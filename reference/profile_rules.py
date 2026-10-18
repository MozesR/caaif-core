"""Example-only THREE-AGENT PROFILE rules. These check fixtures; not a hardened policy engine.

Important: trusted_decisions must come from a trustable server-side store in a live deployment.
Do not pass user-supplied decision objects as that store.
"""
from datetime import datetime, timezone

ROLES = ("conversational", "reasoning", "task")
REQUIRED_PAIRS = {("conversational", "reasoning"), ("reasoning", "task"),
                  ("task", "reasoning"), ("reasoning", "conversational")}


def validate_manifest(manifest):
    roles = manifest["roles"]
    assert set(roles) == set(ROLES), "roles_invalid"
    flattened = [agent for role in ROLES for agent in roles[role]]
    assert all(roles[r] for r in ROLES) and len(flattened) == len(set(flattened)), "roles_not_distinct"
    edges = manifest["allowed_edges"]
    pairs = {(e["from_role"], e["to_role"]) for e in edges}
    assert REQUIRED_PAIRS <= pairs, "missing_required_edges"
    assert pairs == REQUIRED_PAIRS, "undeclared_or_bypass_edge"
    assert len(edges) == len(REQUIRED_PAIRS), "duplicate_or_bypass_edge"
    assert all(manifest["task_guards"].values()), "task_guards_missing"
    return True


def check_request(manifest, contract, request, authenticated_caller, *,
                  trusted_decisions=None, independent_policy_allows=True,
                  now="2026-10-17T15:00:00Z"):
    """Return a boolean for illustrative conformance testing, not an authorization permit."""
    def valid_at(stamp):
        try:
            due = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            current = datetime.fromisoformat(now.replace("Z", "+00:00"))
            return due.tzinfo is not None and current.tzinfo is not None and due > current
        except (ValueError, TypeError, AttributeError):
            return False
    try:
        validate_manifest(manifest)
        if not independent_policy_allows or request["caller_id"] != authenticated_caller:
            return False
        if request["spec_version"] != contract["spec_version"] or not valid_at(request["expires_at"]):
            return False
        if (request["contract_id"], request["contract_version"], request["caller_id"],
            request["recipient_id"], request["capability"]) != (
            contract["contract_id"], contract["version"], contract["caller_id"],
            contract["recipient_id"], contract["capability"]):
            return False
        bind = contract["profile_binding"]
        if bind["profile_id"] != manifest["profile_id"] or bind["profile_version"] != manifest["version"]:
            return False
        a, b = bind["caller_role"], bind["recipient_role"]
        if request["caller_id"] not in manifest["roles"][a] or request["recipient_id"] not in manifest["roles"][b]:
            return False
        matching = any(e["from_role"] == a and e["to_role"] == b and
                       e["contract_id"] == request["contract_id"] and
                       e["capability"] == request["capability"] for e in manifest["allowed_edges"])
        if not matching or not all(ref["scope"] in contract["context_policy"]["allowed_scopes"]
                                   for ref in request["context_refs"]):
            return False
        if (a,b) == ("reasoning","task"):
            record = (trusted_decisions or {}).get(request.get("decision_ref"))
            if not record or not record["authorized"] or not valid_at(record["expires_at"]):
                return False
            if (record["issuer_id"], record["issuer_role"], record["correlation_id"],
                record["recipient_id"], record["capability"], record["contract_id"]) != (
                request["caller_id"], "reasoning", request["correlation_id"], request["recipient_id"],
                request["capability"], request["contract_id"]):
                return False
            if contract["effect"] == "effectful" and not request.get("idempotency_key"):
                return False
        return True
    except (KeyError, AssertionError, TypeError, ValueError):
        return False
