"""CAAIF v0.14 loopback research: bounded intent + online opaque permit.

This module intentionally reuses v0.13's network transport and token-based
*service demo* identities; it does not share a permit-signing key with the
Tool Gateway. On every protected effect the gateway introspects the trusted
Controller, which atomically consumes a random opaque handle once.

SECURITY SCOPE: no TLS, independently managed workload IDs, durable replay
ledger, authenticated end-user confirmation ceremony, multi-node restart safety
or physical tool-path isolation. Only deterministic localhost research evidence.
"""
from __future__ import annotations

import copy
import secrets
import time

from .distributed_guard_v013 import (GuardControllerV013, GuardedToolGatewayV013,
                                     RemoteDenied, post)
from .guarded import _digest
from .local import Denied


class GuardControllerV014(GuardControllerV013):
    """Controller-only random opaque permits; Gateway receives no issuer secret."""

    def __init__(self, *, trusted_parameter_resolvers=None, **kwargs):
        if 'signing_key' in kwargs:
            raise ValueError('v014_does_not_accept_shared_signing_keys')
        # Compatibility with inherited v0.13 HTTP service construction only.
        # The random internal key is never used to create or verify v0.14 permits.
        super().__init__(signing_key=secrets.token_bytes(32), **kwargs)
        self._issued_opaque: dict[str, str] = {}
        self._consumed_opaque: set[str] = set()
        for name, resolver in (trusted_parameter_resolvers or {}).items():
            self._core.register_trusted_parameter_resolver(self._authority, name, resolver)

    def _apply(self, path, p):
        if path == '/trusted/intent' and 'parameter_constraints' in p:
            expected = {'intent_id', 'correlation_id', 'action', 'resource',
                        'parameter_constraints', 'purpose', 'context_refs',
                        'approval_source', 'approval_reference', 'requires_confirmation'}
            if set(p) != expected:
                raise ValueError('invalid_bounded_intent_fields')
            self._core.register_bounded_intent(self._authority,
                intent_id=p['intent_id'], correlation_id=p['correlation_id'],
                action=p['action'], resource=p['resource'],
                parameter_constraints=p['parameter_constraints'], purpose=p['purpose'],
                allowed_context_refs=p['context_refs'], approval_source=p['approval_source'],
                approval_reference=p['approval_reference'],
                requires_confirmation=p['requires_confirmation'])
            return {'registered': True, 'mode': 'bounded-v014'}
        if path == '/trusted/confirm':
            if set(p) != {'proposal_id', 'approved_parameters', 'approval_reference'}:
                raise ValueError('invalid_confirmation_fields')
            self._core.confirm_proposal(self._authority, **p)
            return {'confirmed': True}
        if path == '/trusted/authorize':
            if set(p) != {'proposal_id'}:
                raise ValueError('invalid_authorize_fields')
            permit_id = self._core.authorize_effect(self._authority, p['proposal_id'])
            permit = self._core._permits[permit_id]
            intent = self._core._intents[permit['intent_id']]
            # Physical Provider must independently accept current reads.
            for descriptor in intent['context_refs']:
                self._provider.read(ref=descriptor['ref'], version=descriptor['version'],
                                    scope=descriptor['scope'], correlation_id=intent['correlation_id'])
            token = 'caaif-v014/' + secrets.token_urlsafe(32)
            self._issued_opaque[token] = permit_id
            return {'permit': token, 'expires_at': int(permit['expires'].timestamp())}
        if path == '/introspect':
            if set(p) != {'permit', 'action_request', 'task_principal'}:
                raise ValueError('invalid_introspection_request')
            token = p['permit']
            if not isinstance(token, str) or not token.startswith('caaif-v014/'):
                raise Denied('invalid_opaque_permit')
            permit_id = self._issued_opaque.get(token)
            if not permit_id or token in self._consumed_opaque:
                raise Denied('permit_unknown_or_consumed')
            permit = self._core._permits.get(permit_id)
            if (permit is None or permit_id in self._core._revoked_decisions
                    or permit['tool_used'] or permit['expires'] <= self._core._clock()
                    or permit['policy_version'] != self._core._policy_version):
                raise Denied('permit_expired_or_revoked')
            if p['task_principal'] != permit['recipient']:
                raise Denied('permit_task_mismatch')
            action_request = p['action_request']
            if not isinstance(action_request, dict) or set(action_request) != {
                    'action', 'resource', 'parameters', 'purpose', 'intent_id'}:
                raise Denied('invalid_bound_action')
            if (any(action_request[k] != permit[k] for k in ('action', 'resource', 'purpose', 'intent_id'))
                    or _digest(action_request['parameters']) != permit['parameters_hash']):
                raise Denied('action_binding_mismatch')
            self._core._validated_proposal(self._core._proposals[permit['proposal_id']])
            for descriptor in permit['context_refs']:
                self._provider.read(ref=descriptor['ref'], version=descriptor['version'],
                                    scope=descriptor['scope'], correlation_id=permit['correlation_id'])
            # Atomic, one-time consume under Controller handler's lock.
            # If gateway crashes before execution the result is UNKNOWN, not retried.
            self._consumed_opaque.add(token)
            return {'active': True, 'jti': permit_id, 'action': permit['action'],
                    'resource': permit['resource'], 'context_refs': copy.deepcopy(permit['context_refs']),
                    'correlation_id': permit['correlation_id']}
        return super()._apply(path, p)


class GuardedToolGatewayV014(GuardedToolGatewayV013):
    """Online-introspecting verifier with NO signing or validation key."""

    def __init__(self, **kwargs):
        if 'signing_key' in kwargs:
            raise ValueError('v014_gateway_must_not_receive_issuer_signing_key')
        # Base v0.13 network wrapper expects a signing_key constructor argument,
        # which this v0.14 gateway never uses; it is a fresh unrelated value.
        super().__init__(signing_key=secrets.token_bytes(32), **kwargs)
        self._key = None

    def _execute(self, body):
        if (not isinstance(body, dict) or set(body) != {'permit', 'action_request'}
                or not isinstance(body['action_request'], dict)):
            raise ValueError('invalid_execution_request')
        permit = body['permit']
        action_request = body['action_request']
        if not isinstance(permit, str) or not permit.startswith('caaif-v014/') or len(permit) > 256:
            raise ValueError('invalid_opaque_permit')
        if permit in self._seen:
            raise ValueError('replay_denied')
        if set(action_request) != {'action', 'resource', 'parameters', 'purpose', 'intent_id'}:
            raise ValueError('invalid_action_request')
        # Online lookup both validates and atomically consumes the permit.
        authorized = post(self._controller_url, '/introspect', {
            'permit': permit, 'action_request': action_request,
            'task_principal': self._task_principal}, self._controller_token)
        if (not isinstance(authorized, dict) or authorized.get('active') is not True
                or not isinstance(authorized.get('jti'), str)
                or not authorized['jti']
                or authorized.get('action') != action_request['action']
                or authorized.get('resource') != action_request['resource']):
            raise ValueError('introspection_mismatch')
        for descriptor in authorized['context_refs']:
            self._provider.read(ref=descriptor['ref'], version=descriptor['version'],
                                scope=descriptor['scope'],
                                correlation_id=authorized['correlation_id'])
        operation = self._tools.get(authorized['action'])
        if operation is None:
            raise ValueError('unregistered_tool')
        self._seen.add(permit)
        try:
            outcome = operation(authorized['resource'], copy.deepcopy(action_request['parameters']))
        except Exception:
            # Consumed authorization is never automatically replayed.
            raise
        return {'status': 'completed', 'result': outcome, 'action_id': authorized['jti']}
