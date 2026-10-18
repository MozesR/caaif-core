"""Optional bridge: LocalController + separate context provider (loopback research).

Contracts and caller binding remain with LocalController. Provider owns context
values and independently checks actor/token, grants and read policy. This is
not a network-safe or production-ready workload identity design.
"""
from __future__ import annotations

import copy
import threading
from typing import Mapping

from .local import AgentHandle, Denied, LocalController
from .remote_provider_v09 import ProviderClientV09, ProviderError


class ProviderBackedController(LocalController):
    """Optional context adapter; existing LocalController API remains intact.

    The trusted controller holds a ProviderClientV09 per *bound* recipient ID;
    remote workers receive only short-lived ContextRelay tickets. Context
    values are never replicated into LocalController._contexts.
    """

    def __init__(self, *, provider_clients: Mapping[str, ProviderClientV09], **kwargs):
        super().__init__(**kwargs)
        if not isinstance(provider_clients, Mapping) or not provider_clients:
            raise ValueError("provider_clients_required")
        if any(not isinstance(k, str) or not k or not isinstance(v, ProviderClientV09)
               for k, v in provider_clients.items()):
            raise ValueError("invalid_provider_client")
        self._provider_clients = dict(provider_clients)

    def publish_remote(self, owner: AgentHandle, *, ref: str, version: str,
                       scope: str, value: dict, grants: dict[str, list[str]],
                       correlation_id: str) -> dict:
        """Register metadata locally, publish authoritative values remotely.

        Fail closed and restore local metadata if remote publication fails.
        """
        with self._lock:
            owner_id = self._principal(owner)
            client = self._provider_clients.get(owner_id)
            if client is None:
                self._deny("publisher_not_configured")
            if not isinstance(grants, dict) or not grants:
                raise ValueError("invalid_grants")
            readers = set(grants)
            if not readers <= self._provider_clients.keys():
                raise ValueError("recipient_provider_not_configured")
            old = copy.deepcopy(self._contexts.get(ref))
            descriptor = super().put_context(owner, ref=ref, version=version,
                scope=scope, value={}, readers=readers, correlation_id=correlation_id)
            try:
                published = client.publish(ref=ref, version=version, scope=scope,
                     correlation_id=correlation_id, value=value, grants=grants)
                if published != descriptor:
                    raise ValueError("provider_descriptor_mismatch")
            except Exception:
                if old is None:
                    self._contexts.pop(ref, None)
                else:
                    self._contexts[ref] = old
                raise
            return descriptor

    def _read_provider(self, descriptor: dict, recipient: str, correlation_id: str) -> dict:
        client = self._provider_clients.get(recipient)
        if client is None:
            self._deny("recipient_provider_not_configured")
        try:
            response = client.read(ref=descriptor["ref"], version=descriptor["version"],
                                   scope=descriptor["scope"], correlation_id=correlation_id)
        except ProviderError:
            self._deny("provider_context_denied")
        except Exception:
            self._deny("provider_unavailable")
        if not isinstance(response, dict) or response.get("ref") != descriptor["ref"] or (
                response.get("version") != descriptor["version"] or
                not isinstance(response.get("value"), dict)):
            self._deny("provider_response_invalid")
        return response["value"]

    def _verify_context(self, r: dict, recipient: str, correlation_id: str, contract: dict):
        super()._verify_context(r, recipient, correlation_id, contract)
        # Both here at dispatch-time and later during actual retrieval.
        # Provider revocation/policy changes cannot be bypassed by old refs.
        return self._read_provider(r, recipient, correlation_id)

    def _resolve_context(self, descriptor: dict, recipient: str, correlation_id: str, *, authorized_value=None):
        # The immediately preceding provider check in _ContextView.resolve
        # supplied this result. Avoid a redundant third network retrieval.
        if authorized_value is None:
            return self._read_provider(descriptor, recipient, correlation_id)
        return authorized_value
