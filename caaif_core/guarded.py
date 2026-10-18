"""CAAIF guarded execution proposal proof-of-concept (LOCAL, draft.3).

Untrusted Reasoning proposals never confer authority. Trusted host intent plus an
independent deterministic policy gate issue opaque, action-bound permits.

NOT a network security boundary: handles and records share a trusted Python process.
All effectful tool calls MUST flow through ToolExecutionGateway; arbitrary malicious
Python handlers inside this process can bypass the model-level architecture.
"""
from __future__ import annotations

import copy
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from .local import AgentHandle, Denied, LocalController


def _canon(item: Any) -> bytes:
    return json.dumps(item, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(item: Any) -> str:
    return hashlib.sha256(_canon(item)).hexdigest()


@dataclass(frozen=True)
class ContextProvenance:
    """Metadata is assigned by a trusted host; never taken from model text."""
    source_id: str
    origin_trust: str  # untrusted_external | verified_internal | authenticated_user
    classification: str  # public | internal | confidential | restricted
    allowed_purposes: frozenset[str]
    allowed_recipients: frozenset[str]
    allowed_actions: frozenset[str]
    derived_from: tuple[str, ...] = ()


_CLASS_LEVEL = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_TRUST = {"untrusted_external", "verified_internal", "authenticated_user"}


def merge_provenance(labels: list[ContextProvenance]) -> ContextProvenance:
    """Conservative derived-information label; no declassification here."""
    if not labels:
        raise ValueError("source_labels_required")
    if any(not isinstance(x, ContextProvenance) for x in labels):
        raise ValueError("invalid_source_label")
    return ContextProvenance(
        source_id="derived:" + _digest(sorted(x.source_id for x in labels))[:16],
        origin_trust=("untrusted_external" if any(x.origin_trust == "untrusted_external" for x in labels)
                      else ("verified_internal" if any(x.origin_trust == "verified_internal" for x in labels)
                            else "authenticated_user")),
        classification=max((x.classification for x in labels), key=lambda c: _CLASS_LEVEL[c]),
        allowed_purposes=frozenset.intersection(*(x.allowed_purposes for x in labels)),
        allowed_recipients=frozenset.intersection(*(x.allowed_recipients for x in labels)),
        allowed_actions=frozenset.intersection(*(x.allowed_actions for x in labels)),
        derived_from=tuple(sorted(x.source_id for x in labels)),
    )


class GuardedLocalController(LocalController):
    """A fail-closed local profile, compatible with legacy read-only dispatches.

    The authority argument must be an object held by trusted application code.
    Do not give it to an agent. Object identity is NOT isolation from malicious
    Python running in the same process; use Profile G for deployment isolation.
    """

    def __init__(self, *, authority: object, action_policy: Callable[[dict, dict, tuple], bool],
                 policy_version: str = "policy-v1", **kwargs):
        if authority is None or not callable(action_policy) or not isinstance(policy_version, str) or not policy_version:
            raise ValueError("trusted_authority_and_action_policy_required")
        if kwargs.get("profile") is None:
            raise ValueError("three_agent_profile_required")
        if "effect_policy" in kwargs:
            raise ValueError("external_effect_policy_cannot_override_guard")
        self.__authority = authority
        self._action_policy = action_policy
        self._policy_version = policy_version
        self._intents: dict[str, dict] = {}
        self._provenance: dict[tuple[str, str], ContextProvenance] = {}
        self._proposals: dict[str, dict] = {}
        self._permits: dict[str, dict] = {}
        self._tools: dict[str, Callable[[str, dict], Any]] = {}
        self._trusted_resolvers: dict[str, Callable] = {}
        self._confirmations: dict[str, dict] = {}
        super().__init__(effect_policy=self._guard_effect_policy, **kwargs)

    def _require_authority(self, authority: object) -> None:
        if authority is not self.__authority:
            self._deny("trusted_authority_required")

    def issue_decision(self, *args, **kwargs):
        """Disable the original model-supplied authorized=True path."""
        self._deny("legacy_decision_issuer_disabled")

    def register_intent(self, authority: object, *, intent_id: str, correlation_id: str,
                        action: str, resource: str, parameters: dict, purpose: str,
                        allowed_context_refs: list[dict], ttl_seconds: int = 300) -> None:
        self._require_authority(authority)
        if not all(isinstance(x, str) and x for x in (intent_id, correlation_id, action, resource, purpose)):
            raise ValueError("invalid_trusted_intent")
        if (type(ttl_seconds) is not int or ttl_seconds < 1 or ttl_seconds > 3600
                or not isinstance(parameters, dict) or not isinstance(allowed_context_refs, list)):
            raise ValueError("invalid_trusted_intent")
        if intent_id in self._intents:
            raise ValueError("trusted_intent_immutable")
        if any(not isinstance(r, dict) or set(r) != {"ref", "version", "scope"} for r in allowed_context_refs):
            raise ValueError("invalid_context_descriptors")
        with self._lock:
            self._intents[intent_id] = {
                "intent_id": intent_id, "correlation_id": correlation_id, "action": action,
                "resource": resource, "parameters": copy.deepcopy(parameters),
                "purpose": purpose, "context_refs": copy.deepcopy(allowed_context_refs),
                "expires": self._clock() + timedelta(seconds=ttl_seconds),
            }
            self._event("trusted_intent_registered")

    def register_trusted_parameter_resolver(self, authority: object, resolver_id: str,
                                            resolver: Callable) -> None:
        """Install a host-owned evidence lookup (not an agent-supplied callback)."""
        self._require_authority(authority)
        if not isinstance(resolver_id, str) or not resolver_id or not callable(resolver):
            raise ValueError("invalid_parameter_resolver")
        with self._lock:
            if resolver_id in self._trusted_resolvers:
                raise ValueError("duplicate_parameter_resolver")
            self._trusted_resolvers[resolver_id] = resolver

    def register_bounded_intent(self, authority: object, *, intent_id: str,
                                correlation_id: str, action: str, resource: str,
                                parameter_constraints: dict, purpose: str,
                                allowed_context_refs: list[dict], approval_source: str,
                                approval_reference: str,
                                requires_confirmation: bool = False,
                                ttl_seconds: int = 300) -> None:
        """Register user/host-approved LIMITS, not LLM-generated permissions.

        approval_reference identifies a host-verifiable source action. This
        local library cannot establish that the user actually approved it;
        the application's authenticated approval service must do so.
        """
        from .intent_v014 import validate_rules, validate_approval
        self._require_authority(authority)
        validate_approval(approval_source, approval_reference)
        if (not all(isinstance(x, str) and x for x in
                    (intent_id, correlation_id, action, resource, purpose))
                or type(requires_confirmation) is not bool or type(ttl_seconds) is not int
                or ttl_seconds < 1 or ttl_seconds > 3600
                or not isinstance(allowed_context_refs, list)
                or len(allowed_context_refs) > 16
                or any(not isinstance(ref, dict) or set(ref) != {"ref", "version", "scope"}
                       or any(not isinstance(v, str) or not v for v in ref.values())
                       for ref in allowed_context_refs)):
            raise ValueError("invalid_bounded_intent")
        constraints = validate_rules(parameter_constraints)
        with self._lock:
            if intent_id in self._intents:
                raise ValueError("trusted_intent_immutable")
            self._intents[intent_id] = {
                "intent_id": intent_id, "correlation_id": correlation_id,
                "action": action, "resource": resource, "purpose": purpose,
                "context_refs": copy.deepcopy(allowed_context_refs),
                "parameter_constraints": constraints, "intent_mode": "bounded-v014",
                "approval_source": approval_source, "approval_reference": approval_reference,
                "requires_confirmation": requires_confirmation,
                "expires": self._clock() + timedelta(seconds=ttl_seconds),
            }
            self._event("bounded_intent_registered")

    def confirm_proposal(self, authority: object, *, proposal_id: str,
                         approved_parameters: dict, approval_reference: str,
                         ttl_seconds: int = 120) -> None:
        """Trusted host confirms the exact model-proposed values AFTER proposal.

        A user-facing integration must independently authenticate the approver
        and display the exact values, rather than approving an LLM paraphrase.
        """
        self._require_authority(authority)
        if (not isinstance(approved_parameters, dict) or not isinstance(approval_reference, str)
                or not approval_reference.strip() or len(approval_reference) > 256
                or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 600):
            raise ValueError("invalid_confirmation")
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None or proposal_id in self._confirmations:
                self._deny("confirmation_unknown_or_immutable")
            intent = self._intents.get(proposal["intent_id"])
            if not intent or intent.get("intent_mode") != "bounded-v014" or not intent["requires_confirmation"]:
                self._deny("confirmation_not_applicable")
            if _canon(approved_parameters) != _canon(proposal["parameters"]):
                self._deny("confirmation_parameters_mismatch")
            self._confirmations[proposal_id] = {
                "parameters_hash": _digest(approved_parameters),
                "approval_reference": approval_reference,
                "expires": min(self._clock() + timedelta(seconds=ttl_seconds), intent["expires"]),
            }
            self._event("exact_parameters_confirmed")

    def revoke_confirmation(self, authority: object, proposal_id: str) -> None:
        self._require_authority(authority)
        with self._lock:
            self._confirmations.pop(proposal_id, None)
            self._event("confirmation_revoked")

    def label_context(self, authority: object, *, ref: str, version: str,
                      label: ContextProvenance) -> None:
        self._require_authority(authority)
        if not isinstance(label, ContextProvenance) or label.origin_trust not in _TRUST or label.classification not in _CLASS_LEVEL:
            raise ValueError("invalid_provenance")
        if (not label.source_id or not label.allowed_purposes or not label.allowed_recipients
                or not label.allowed_actions or any(not isinstance(v, str) or not v for v in (
                    *label.allowed_purposes, *label.allowed_recipients, *label.allowed_actions))):
            raise ValueError("invalid_provenance")
        with self._lock:
            item = self._contexts.get(ref)
            if item is None or item["version"] != version or item["revoked"]:
                self._deny("context_not_current")
            if (ref, version) in self._provenance:
                raise ValueError("provenance_immutable")
            self._provenance[(ref, version)] = label
            self._event("context_provenance_registered")

    def propose_effect(self, issuer: AgentHandle, *, intent_id: str, contract_id: str,
                       action: str, resource: str, parameters: dict, purpose: str,
                       context_refs: list[dict]) -> str:
        """Receive a model-originated PROPOSAL; this is not an authorization."""
        with self._lock:
            agent_id = self._principal(issuer)
            if agent_id not in self.profile["roles"]["reasoning"]:
                self._deny("proposal_requires_reasoning")
            if not all(isinstance(x, str) and x for x in (intent_id, contract_id, action, resource, purpose)):
                raise ValueError("invalid_proposal")
            if not isinstance(parameters, dict) or not isinstance(context_refs, list):
                raise ValueError("invalid_proposal")
            if len(_canon(parameters)) > 8192 or len(context_refs) > 16:
                raise ValueError("proposal_too_large")
            proposal_id = "proposal:local/" + secrets.token_hex(12)
            self._proposals[proposal_id] = {
                "proposal_id": proposal_id, "issuer": agent_id, "intent_id": intent_id,
                "contract_id": contract_id, "action": action, "resource": resource,
                "parameters": copy.deepcopy(parameters), "purpose": purpose,
                "context_refs": copy.deepcopy(context_refs),
            }
            self._event("untrusted_proposal_received")
            return proposal_id

    def _validated_proposal(self, proposal: dict) -> tuple[dict, dict, tuple[ContextProvenance, ...], dict]:
        intent = self._intents.get(proposal["intent_id"])
        if intent is None or intent["expires"] <= self._clock():
            self._deny("intent_missing_or_expired")
        contract_candidates = [c for (_, _), c in self._contracts.items()
                               if c["contract_id"] == proposal["contract_id"]]
        if len(contract_candidates) != 1:
            self._deny("contract_ambiguous_or_missing")
        contract = contract_candidates[0]
        if ((contract["contract_id"], contract["version"]) in self._revoked_contracts
                or contract["effect"] != "effectful" or contract["caller_id"] != proposal["issuer"]
                or contract["recipient_id"] not in self.profile["roles"]["task"]
                or contract["capability"] != "task.execute"):
            self._deny("contract_not_guardable")
        for field in ("action", "resource", "purpose"):
            if proposal[field] != intent[field]:
                self._deny("proposal_outside_trusted_intent")
        if intent.get("intent_mode") != "bounded-v014":
            if proposal["parameters"] != intent["parameters"]:
                self._deny("proposal_outside_trusted_intent")
        if proposal["context_refs"] != intent["context_refs"]:
            self._deny("proposal_context_outside_intent")
        labels = []
        for descriptor in proposal["context_refs"]:
            if not isinstance(descriptor, dict) or set(descriptor) != {"ref", "version", "scope"}:
                self._deny("invalid_context_descriptor")
            self._verify_context(descriptor, contract["recipient_id"], intent["correlation_id"], contract)
            label = self._provenance.get((descriptor["ref"], descriptor["version"]))
            if label is None:
                self._deny("missing_trusted_provenance")
            if (proposal["purpose"] not in label.allowed_purposes or
                    contract["recipient_id"] not in label.allowed_recipients or
                    proposal["action"] not in label.allowed_actions):
                self._deny("provenance_policy_denied")
            labels.append(label)
        if intent.get("intent_mode") == "bounded-v014":
            from .intent_v014 import check_parameters
            if not check_parameters(proposal["parameters"], intent["parameter_constraints"],
                                    proposal=proposal, labels=tuple(labels),
                                    trusted_resolvers=self._trusted_resolvers):
                self._deny("proposal_outside_intent_constraints")
            if intent["requires_confirmation"]:
                confirmation = self._confirmations.get(proposal["proposal_id"])
                if (confirmation is None or confirmation["expires"] <= self._clock()
                        or confirmation["parameters_hash"] != _digest(proposal["parameters"])):
                    self._deny("exact_parameter_confirmation_required")
        try:
            allowed = self._action_policy(copy.deepcopy(proposal), copy.deepcopy({k:v for k,v in intent.items() if k != "expires"}), tuple(labels))
        except Exception:
            self._deny("independent_policy_unavailable")
        if allowed is not True:
            self._deny("independent_policy_denied")
        return intent, contract, tuple(labels), proposal

    def authorize_effect(self, authority: object, proposal_id: str, *, ttl_seconds: int = 30) -> str:
        self._require_authority(authority)
        if type(ttl_seconds) is not int or ttl_seconds < 1 or ttl_seconds > 60:
            raise ValueError("invalid_permit_ttl")
        with self._lock:
            p = self._proposals.get(proposal_id)
            if p is None:
                self._deny("unknown_proposal")
            if any(x["proposal_id"] == proposal_id for x in self._permits.values()):
                self._deny("proposal_already_authorized")
            intent, contract, _, p = self._validated_proposal(p)
            deadline = min(self._clock() + timedelta(seconds=ttl_seconds), intent["expires"])
            permit_id = "permit:local/" + secrets.token_urlsafe(24)
            self._permits[permit_id] = {
                "proposal_id": proposal_id, "action": p["action"], "resource": p["resource"],
                "parameters_hash": _digest(p["parameters"]), "purpose": p["purpose"],
                "intent_id": p["intent_id"], "context_refs": copy.deepcopy(p["context_refs"]),
                "issuer": p["issuer"], "recipient": contract["recipient_id"],
                "contract_id": p["contract_id"], "contract_version": contract["version"],
                "correlation_id": intent["correlation_id"], "audience": "local-tool-gateway",
                "nonce": secrets.token_urlsafe(16), "policy_version": self._policy_version,
                "expires": deadline, "bound_request_id": None, "tool_used": False,
            }
            # Compatibility with the draft.2 InteractionRequest.decision_ref field.
            # This is an INDEPENDENTLY ISSUED PERMIT, not an LLM decision record.
            self._decisions[permit_id] = {
                "issuer": p["issuer"], "correlation_id": intent["correlation_id"],
                "contract_id": p["contract_id"], "recipient": contract["recipient_id"],
                "capability": "task.execute", "expires": deadline,
            }
            self._event("independent_permit_issued")
            return permit_id

    def new_guarded_request(self, issuer: AgentHandle, permit_id: str, *,
                            idempotency_key: str, request_id: str | None = None) -> dict:
        with self._lock:
            issuer_id = self._principal(issuer)
            permit = self._permits.get(permit_id)
            if not permit or permit["issuer"] != issuer_id:
                self._deny("permit_issuer_mismatch")
            proposal = self._proposals[permit["proposal_id"]]
            return self.new_request(issuer, contract_id=permit["contract_id"],
                       correlation_id=permit["correlation_id"], context_refs=permit["context_refs"],
                       decision_ref=permit_id, idempotency_key=idempotency_key,
                       request_id=request_id,
                       data={"action": permit["action"], "resource": permit["resource"],
                             "parameters": copy.deepcopy(proposal["parameters"]),
                             "purpose": permit["purpose"], "intent_id": permit["intent_id"]})

    def _guard_effect_policy(self, request: dict, contract: dict) -> bool:
        """Independent of the LLM. Called by LocalController.dispatch, deny by default."""
        permit_id = request.get("decision_ref")
        permit = self._permits.get(permit_id)
        if permit is None or permit_id in self._revoked_decisions:
            return False
        if (permit["policy_version"] != self._policy_version or permit["expires"] <= self._clock()
                or request["caller_id"] != permit["issuer"]
                or contract["recipient_id"] != permit["recipient"]
                or contract["contract_id"] != permit["contract_id"]
                or contract["version"] != permit["contract_version"]
                or request["correlation_id"] != permit["correlation_id"]
                or request["context_refs"] != permit["context_refs"]):
            return False
        input_data = request.get("input", {})
        if (set(input_data) != {"action", "resource", "parameters", "purpose", "intent_id"}
                or any(input_data.get(k) != permit[k] for k in ("action", "resource", "purpose", "intent_id"))
                or _digest(input_data["parameters"]) != permit["parameters_hash"]):
            return False
        bound = permit["bound_request_id"]
        if bound is not None and bound != request["request_id"]:
            return False
        # Fresh independent policy and authoritative intent/provenance checks at use.
        try:
            self._validated_proposal(self._proposals[permit["proposal_id"]])
        except Denied:
            return False
        if bound is None:
            permit["bound_request_id"] = request["request_id"]
        return True

    def register_trusted_tool(self, authority: object, action: str,
                              executor: Callable[[str, dict], Any]) -> None:
        """Only trusted host code installs effectful tool implementations."""
        self._require_authority(authority)
        if not isinstance(action, str) or not action or not callable(executor):
            raise ValueError("invalid_tool_registration")
        if action in self._tools:
            raise ValueError("duplicate_tool_registration")
        self._tools[action] = executor

    def tool_gateway_execute(self, task: AgentHandle, request: dict) -> Any:
        """Trusted gateway dispatches a specific authorized action.

        The Task Agent cannot submit arbitrary executable callbacks. This is a
        local-only demonstration: production requires an isolated gateway with
        authenticated tool credentials and no direct bypass path.
        """
        with self._lock:
            task_id = self._principal(task)
            permit_id = request.get("decision_ref")
            permit = self._permits.get(permit_id)
            inp = request.get("input", {})
            valid = (permit is not None and permit_id not in self._revoked_decisions
                     and task_id == permit["recipient"]
                     and permit["audience"] == "local-tool-gateway"
                     and permit["bound_request_id"] == request.get("request_id")
                     and not permit["tool_used"]
                     and permit["policy_version"] == self._policy_version
                     and permit["expires"] > self._clock()
                     and isinstance(inp, dict) and set(inp) == {
                         "action", "resource", "parameters", "purpose", "intent_id"}
                     and all(inp[k] == permit[k] for k in (
                         "action", "resource", "purpose", "intent_id"))
                     and _digest(inp["parameters"]) == permit["parameters_hash"]
                     and request.get("correlation_id") == permit["correlation_id"]
                     and request.get("contract_id") == permit["contract_id"]
                     and request.get("contract_version") == permit["contract_version"]
                     and request.get("context_refs") == permit["context_refs"])
            if not valid:
                self._deny("tool_execution_not_permitted", request.get("request_id", ""))
            try:
                self._validated_proposal(self._proposals[permit["proposal_id"]])
            except Denied:
                self._deny("tool_policy_no_longer_valid", request.get("request_id", ""))
            operation = self._tools.get(permit["action"])
            if operation is None:
                self._deny("tool_not_registered", request.get("request_id", ""))
            permit["tool_used"] = True
            resource = permit["resource"]
            params = copy.deepcopy(inp["parameters"])
            self._event("tool_gate_authorized", request.get("request_id", ""))
        # An ambiguous tool result is never automatically retried.
        try:
            return operation(resource, params)
        except Exception:
            with self._lock:
                self._event("tool_outcome_unknown", request.get("request_id", ""))
            raise

    def authorize_disclosure(self, authority: object, *, context_refs: list[dict],
                             recipient: str, purpose: str) -> ContextProvenance:
        """Conservative release check for the declared sources; caller must route egress here.

        The caller must supply the COMPLETE lineage from a trusted runtime.
        Content-based inference of model provenance is out of scope.
        """
        self._require_authority(authority)
        if not context_refs:
            raise Denied("unknown_disclosure_lineage")
        labels = []
        for ref in context_refs:
            label = self._provenance.get((ref["ref"], ref["version"]))
            if (label is None or ref["ref"] not in self._contexts or
                    self._contexts[ref["ref"]]["revoked"] or
                    self._contexts[ref["ref"]]["version"] != ref["version"]):
                self._deny("disclosure_source_unavailable")
            labels.append(label)
        merged = merge_provenance(labels)
        if recipient not in merged.allowed_recipients or purpose not in merged.allowed_purposes:
            self._deny("disclosure_denied")
        self._event("disclosure_authorized")
        return merged

    def revoke_permit(self, authority: object, permit_id: str) -> None:
        self._require_authority(authority)
        self._revoked_decisions.add(permit_id)
        self._event("permit_revoked")

    def rotate_policy(self, authority: object, version: str) -> None:
        self._require_authority(authority)
        if not isinstance(version, str) or not version:
            raise ValueError("invalid_policy_version")
        self._policy_version = version
        self._event("policy_rotated")
