"""Minimal local CAAIF boundary, implementing draft.2 interaction semantics.

This is NOT an authenticated distributed gateway. Caller identity is bound to
opaque handle *object identity* in one trusted Python process. No network or
OS security boundary is asserted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

SPEC_VERSION = "1.0.0-draft.2"
ROLE_EDGES = {
    ("conversational", "reasoning", "intent.assess"),
    ("reasoning", "task", "task.execute"),
    ("task", "reasoning", "task.report"),
    ("reasoning", "conversational", "response.compose"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _time(stamp: str) -> datetime:
    if not isinstance(stamp, str):
        raise ValueError("invalid_timestamp")
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive_timestamp")
    return dt


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


class Denied(Exception):
    """Machine-readable local policy denial; no request data included."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, eq=False)
class AgentHandle:
    agent_id: str
    # Object-identity binding is intentionally local-only.


class _ContextView:
    def __init__(self, controller: "LocalController", recipient: str, request: dict, contract: dict):
        self._controller = controller
        self._recipient = recipient
        self._request = request
        self._contract = contract
        self.used_versions: dict[str, str] = {}

    def resolve(self, ref: str) -> Any:
        declared = [r for r in self._request["context_refs"] if r["ref"] == ref]
        if len(declared) != 1:
            raise Denied("undeclared_context_ref")
        descriptor = declared[0]
        authorized_value = self._controller._verify_context(descriptor, self._recipient,
                                         self._request["correlation_id"], self._contract)
        self.used_versions[ref] = descriptor["version"]
        self._controller._event("context_resolved", self._request["request_id"])
        return copy.deepcopy(self._controller._resolve_context(descriptor, self._recipient, self._request["correlation_id"], authorized_value=authorized_value))


class LocalController:
    """In-process CAAIF prototype with no persistence or network dependencies."""
    def __init__(self, *, contracts: list[dict], policy: Callable[[dict, dict], bool],
                 profile: dict | None = None,
                 effect_policy: Callable[[dict, dict], bool] | None = None,
                 clock: Callable[[], datetime] = _now):
        if not callable(policy):
            raise ValueError("policy_required")
        self._policy = policy
        self._effect_policy = effect_policy
        self._clock = clock
        self._lock = threading.RLock()
        self._handlers: dict[str, Callable[[dict, _ContextView], dict]] = {}
        self._handles: dict[str, AgentHandle] = {}
        self._contracts = {}
        self._contexts = {}
        self._decisions = {}
        self._requests = {}
        self._effects = {}
        self._revoked_contracts = set()
        self._revoked_decisions = set()
        self.events: list[dict[str, str]] = []
        self.profile = copy.deepcopy(profile)
        if self.profile is not None:
            self._validate_profile(self.profile)
        for contract in contracts:
            key = (contract["contract_id"], contract["version"])
            if key in self._contracts:
                raise ValueError("duplicate_contract")
            if self.profile:
                self._check_contract_binding(contract)
            self._contracts[key] = copy.deepcopy(contract)

    @staticmethod
    def _validate_profile(profile: dict) -> None:
        roles = profile["roles"]
        if set(roles) != {"conversational", "reasoning", "task"}:
            raise ValueError("profile_roles_invalid")
        ids = [i for agents in roles.values() for i in agents]
        if not ids or not all(roles.values()) or len(ids) != len(set(ids)):
            raise ValueError("profile_roles_not_distinct")
        edges = profile["allowed_edges"]
        triples = {(e["from_role"], e["to_role"], e["capability"]) for e in edges}
        if triples != ROLE_EDGES or len(edges) != len(ROLE_EDGES):
            raise ValueError("profile_edges_invalid")
        if not all(profile["task_guards"].get(k) is True for k in (
                "require_trusted_reasoning_decision", "independent_dispatch_policy",
                "forbid_conversational_to_task")):
            raise ValueError("profile_guards_invalid")

    def _check_contract_binding(self, contract: dict) -> None:
        binding = contract.get("profile_binding")
        if not isinstance(binding, dict):
            raise ValueError("profile_binding_required")
        a, b = binding["caller_role"], binding["recipient_role"]
        if (binding["profile_id"], binding["profile_version"]) != (
                self.profile["profile_id"], self.profile["version"]):
            raise ValueError("profile_binding_mismatch")
        if ((a, b, contract["capability"]) not in ROLE_EDGES
                or contract["caller_id"] not in self.profile["roles"][a]
                or contract["recipient_id"] not in self.profile["roles"][b]):
            raise ValueError("forbidden_profile_contract")
        edge = any(e["from_role"] == a and e["to_role"] == b
                   and e["contract_id"] == contract["contract_id"]
                   and e["capability"] == contract["capability"]
                   for e in self.profile["allowed_edges"])
        if not edge:
            raise ValueError("undeclared_profile_edge")

    def _event(self, event: str, request_id: str = "", reason: str = "") -> None:
        # No input, context, credentials, or reasoning contents are logged.
        self.events.append({"event": event, "request_id": request_id, "reason": reason})

    def _deny(self, code: str, request_id: str = "") -> None:
        self._event("denied", request_id, code)
        raise Denied(code)

    def attach(self, agent_id: str, handler: Callable[[dict, _ContextView], dict]) -> AgentHandle:
        if not isinstance(agent_id, str) or not agent_id or not callable(handler):
            raise ValueError("invalid_agent")
        if self.profile and not any(agent_id in ids for ids in self.profile["roles"].values()):
            raise ValueError("agent_not_in_profile")
        if agent_id in self._handles:
            raise ValueError("duplicate_agent")
        handle = AgentHandle(agent_id)
        self._handles[agent_id] = handle
        self._handlers[agent_id] = handler
        return handle

    def _principal(self, handle: AgentHandle) -> str:
        if not isinstance(handle, AgentHandle) or self._handles.get(handle.agent_id) is not handle:
            self._deny("caller_not_bound")
        return handle.agent_id

    def put_context(self, owner: AgentHandle, *, ref: str, version: str, scope: str,
                    value: Any, readers: set[str], correlation_id: str) -> dict:
        owner_id = self._principal(owner)
        if not all(isinstance(x, str) and x for x in (ref, version, scope, correlation_id)):
            raise ValueError("invalid_context_metadata")
        if not readers or not set(readers) <= self._handles.keys():
            raise ValueError("unknown_context_reader")
        if ref in self._contexts and self._contexts[ref]["owner"] != owner_id:
            raise Denied("context_owner_mismatch")
        if ref in self._contexts and self._contexts[ref]["version"] == version:
            raise Denied("immutable_context_version")
        self._contexts[ref] = {"version": version, "scope": scope,
                               "value": copy.deepcopy(value), "readers": set(readers),
                               "correlation_id": correlation_id, "owner": owner_id,
                               "revoked": False}
        return {"ref": ref, "version": version, "scope": scope}

    def revoke_context(self, ref: str) -> None:
        if ref in self._contexts:
            self._contexts[ref]["revoked"] = True

    def revoke_contract(self, contract_id: str, version: str) -> None:
        self._revoked_contracts.add((contract_id, version))

    def revoke_decision(self, ref: str) -> None:
        self._revoked_decisions.add(ref)

    def _verify_context(self, r: dict, recipient: str, correlation_id: str, contract: dict) -> None:
        item = self._contexts.get(r["ref"])
        if item is None or item["revoked"]:
            self._deny("context_unavailable")
        if item["version"] != r["version"]:
            self._deny("context_version_conflict")
        if item["scope"] != r["scope"] or r["scope"] not in contract["context_policy"]["allowed_scopes"]:
            self._deny("context_scope_denied")
        if recipient not in item["readers"] or correlation_id != item["correlation_id"]:
            self._deny("context_reader_denied")

    def _resolve_context(self, descriptor: dict, recipient: str, correlation_id: str, *, authorized_value=None):
        """Overridable context retrieval hook (default: local storage)."""
        return self._contexts[descriptor["ref"]]["value"]

    def issue_decision(self, issuer: AgentHandle, *, correlation_id: str,
                       contract_id: str, recipient_id: str, capability: str,
                       authorized: bool, ttl_seconds: int = 30) -> str:
        issuer_id = self._principal(issuer)
        if not self.profile or issuer_id not in self.profile["roles"]["reasoning"]:
            self._deny("issuer_not_reasoning")
        contract = next((c for (cid, _), c in self._contracts.items()
                         if cid == contract_id and c["recipient_id"] == recipient_id
                         and c["caller_id"] == issuer_id and c["capability"] == capability), None)
        if not contract or contract["effect"] != "effectful" or not authorized:
            self._deny("decision_not_authorized")
        if not isinstance(ttl_seconds, int) or not 0 < ttl_seconds <= contract["limits"]["ttl_seconds"]:
            raise ValueError("invalid_decision_ttl")
        ref = "decision:local/" + secrets.token_hex(12)
        self._decisions[ref] = {"issuer": issuer_id, "correlation_id": correlation_id,
                                "contract_id": contract_id, "recipient": recipient_id,
                                "capability": capability,
                                "expires": self._clock() + timedelta(seconds=ttl_seconds)}
        self._event("decision_issued")
        return ref

    def new_request(self, caller: AgentHandle, *, contract_id: str, correlation_id: str,
                    context_refs: list[dict] | None = None, data: dict | None = None,
                    decision_ref: str | None = None, idempotency_key: str | None = None,
                    request_id: str | None = None, ttl_seconds: int = 30) -> dict:
        caller_id = self._principal(caller)
        matches = [c for (cid, _), c in self._contracts.items() if cid == contract_id]
        if len(matches) != 1:
            raise ValueError("unknown_or_ambiguous_contract")
        contract = matches[0]
        if ttl_seconds <= 0 or ttl_seconds > contract["limits"]["ttl_seconds"]:
            raise ValueError("invalid_request_ttl")
        result = {"spec_version": SPEC_VERSION, "request_id": request_id or "req-" + secrets.token_hex(12),
                  "correlation_id": correlation_id, "contract_id": contract_id,
                  "contract_version": contract["version"], "caller_id": caller_id,
                  "recipient_id": contract["recipient_id"], "capability": contract["capability"],
                  "context_refs": copy.deepcopy(context_refs or []), "input": copy.deepcopy(data or {}),
                  "expires_at": _stamp(self._clock() + timedelta(seconds=ttl_seconds))}
        if decision_ref is not None:
            result["decision_ref"] = decision_ref
        if idempotency_key is not None:
            result["idempotency_key"] = idempotency_key
        return result

    def dispatch(self, caller: AgentHandle, request: dict) -> dict:
        request_id = request.get("request_id", "") if isinstance(request, dict) else ""
        with self._lock:
            agent_id = self._principal(caller)
            if not isinstance(request, dict) or request.get("spec_version") != SPEC_VERSION:
                self._deny("invalid_envelope", request_id)
            key = (request.get("contract_id"), request.get("contract_version"))
            contract = self._contracts.get(key)
            if contract is None or key in self._revoked_contracts:
                self._deny("unknown_or_revoked_contract", request_id)
            if (request.get("caller_id") != agent_id or agent_id != contract["caller_id"] or
                    any(request.get(k) != contract[v] for k, v in (
                        ("recipient_id", "recipient_id"), ("capability", "capability"),
                        ("contract_id", "contract_id"), ("contract_version", "version")))):
                self._deny("contract_or_identity_mismatch", request_id)
            if not isinstance(request.get("input"), dict) or not isinstance(request.get("context_refs"), list):
                self._deny("invalid_request_data", request_id)
            if not isinstance(request_id, str) or not request_id:
                self._deny("missing_request_id")
            if not isinstance(request.get("correlation_id"), str) or not request["correlation_id"]:
                self._deny("missing_correlation", request_id)
            if len(_json(request)) > contract["limits"]["max_request_bytes"]:
                self._deny("request_too_large", request_id)
            if len(_json(request["input"])) > contract["context_policy"]["max_inline_bytes"]:
                self._deny("inline_context_too_large", request_id)
            deadline = _time(request.get("expires_at"))
            delta = (deadline - self._clock()).total_seconds()
            if delta <= 0 or delta > contract["limits"]["ttl_seconds"] + 1:
                self._deny("expired_or_overlong_request", request_id)
            refs = request["context_refs"]
            if len(refs) > contract["context_policy"]["max_refs"]:
                self._deny("too_many_context_refs", request_id)
            if any(not isinstance(r, dict) or set(r) != {"ref", "version", "scope"} for r in refs):
                self._deny("invalid_context_ref", request_id)
            if len({r["ref"] for r in refs}) != len(refs):
                self._deny("duplicate_context_ref", request_id)
            for r in refs:
                self._verify_context(r, contract["recipient_id"], request["correlation_id"], contract)
            if self.profile:
                # Contract was prechecked against profile, including no bypass edges.
                self._check_contract_binding(contract)
            try:
                allowed = self._policy(request, contract)
            except Exception:
                self._deny("policy_unavailable", request_id)
            if allowed is not True:
                self._deny("policy_denied", request_id)
            if contract["effect"] == "effectful" and self.profile:
                record = self._decisions.get(request.get("decision_ref"))
                if request.get("decision_ref") in self._revoked_decisions or not record or (
                    record["issuer"] != agent_id or record["correlation_id"] != request["correlation_id"]
                    or record["contract_id"] != contract["contract_id"]
                    or record["recipient"] != contract["recipient_id"]
                    or record["capability"] != contract["capability"]
                    or record["expires"] <= self._clock()
                ):
                    self._deny("reasoning_decision_invalid", request_id)
            if contract["effect"] == "effectful":
                if not request.get("idempotency_key"):
                    self._deny("idempotency_required", request_id)
                if self._effect_policy is None:
                    self._deny("effect_policy_missing", request_id)
                try:
                    effect_allowed = self._effect_policy(request, contract)
                except Exception:
                    self._deny("effect_policy_unavailable", request_id)
                if effect_allowed is not True:
                    self._deny("effect_policy_denied", request_id)
            fingerprint = _hash(request)
            prev = self._requests.get(request_id)
            if prev is not None:
                if prev["digest"] != fingerprint:
                    self._deny("request_id_conflict", request_id)
                if prev["status"] != "completed":
                    self._deny("outcome_unknown", request_id)
                return copy.deepcopy(prev["result"])
            if contract["recipient_id"] not in self._handlers:
                self._deny("recipient_unavailable", request_id)
            effect_key = None
            if contract["effect"] == "effectful":
                effect_key = (contract["recipient_id"], request["idempotency_key"])
                prior_effect = self._effects.get(effect_key)
                if prior_effect is not None:
                    self._deny("effect_already_reserved", request_id)
                self._effects[effect_key] = "pending"
            self._requests[request_id] = {"digest": fingerprint, "status": "pending"}
            self._event("allowed", request_id)
            self._event("dispatched", request_id)
            recipient = self._handlers[contract["recipient_id"]]
            ctx = _ContextView(self, contract["recipient_id"], request, contract)
        try:
            payload = recipient(copy.deepcopy(request), ctx)
            if not isinstance(payload, dict):
                raise TypeError("recipient_result_not_object")
            result = {"spec_version": SPEC_VERSION, "request_id": request_id,
                      "status": "completed", "output": copy.deepcopy(payload),
                      "completed_at": _stamp(self._clock()),
                      "used_context_versions": ctx.used_versions}
        except Exception:
            with self._lock:
                self._event("failed", request_id, "recipient_failure")
            # Remains pending, i.e. unknown outcome until reconciled.
            raise
        with self._lock:
            self._requests[request_id] = {"digest": fingerprint, "status": "completed", "result": result}
            if effect_key:
                self._effects[effect_key] = "completed"
            self._event("completed", request_id)
        return copy.deepcopy(result)
