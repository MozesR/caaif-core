"""CAAIF v0.14 constrained intent validation (LOCAL RESEARCH PROFILE).

The agent chooses values; independently controlled rule objects constrain them.
Trusted host confirmation must occur *after* a concrete proposal for actions that
require a user's exact-value approval. This library cannot authenticate a UI or
prove who clicked it: the host integration is in the trusted computing base.

No eval, wildcards, arbitrary model-authored predicates or implicit coercions.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .guarded import _canon, _digest

_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$")
_ALLOWED_APPROVALS = frozenset({"structured_user_action", "verified_host_policy"})


@dataclass(frozen=True)
class VerifiedParameter:
    """Trusted resolver output. A model cannot create a trusted resolver result."""
    value: Any
    source_id: str
    source_version: str


def _money(value: Any) -> Decimal:
    """Only canonical decimal strings are accepted; no floats or bools."""
    if not isinstance(value, str) or _DECIMAL.fullmatch(value) is None:
        raise ValueError("invalid_decimal_string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid_decimal_string") from exc
    if not result.is_finite():
        raise ValueError("invalid_decimal_string")
    return result


def validate_rules(raw: dict) -> dict:
    """Validate a small, immutable-by-copy, deny-by-default ruleset."""
    if (not isinstance(raw, dict) or len(raw) > 24 or
            any(not isinstance(name, str) or not name or len(name) > 80 for name in raw)):
        raise ValueError("invalid_intent_constraints")
    if len(_canon(raw)) > 8192:
        raise ValueError("intent_constraints_too_large")
    checked = copy.deepcopy(raw)
    for name, rule in checked.items():
        if not isinstance(rule, dict) or "kind" not in rule:
            raise ValueError("invalid_parameter_rule")
        kind = rule["kind"]
        if kind == "exact":
            if set(rule) != {"kind", "value"}:
                raise ValueError("invalid_parameter_rule")
        elif kind == "one_of":
            if set(rule) != {"kind", "values"} or not isinstance(rule["values"], list) or not 1 <= len(rule["values"]) <= 64:
                raise ValueError("invalid_parameter_rule")
            if len({_digest(v) for v in rule["values"]}) != len(rule["values"]):
                raise ValueError("duplicate_parameter_options")
        elif kind == "decimal_range":
            if set(rule) != {"kind", "minimum", "maximum"}:
                raise ValueError("invalid_parameter_rule")
            if _money(rule["minimum"]) > _money(rule["maximum"]):
                raise ValueError("invalid_parameter_range")
        elif kind == "trusted_lookup":
            if (set(rule) != {"kind", "resolver", "source_id"}
                    or not isinstance(rule["resolver"], str) or not rule["resolver"]
                    or not isinstance(rule["source_id"], str) or not rule["source_id"]):
                raise ValueError("invalid_parameter_rule")
        else:
            raise ValueError("unrecognized_parameter_rule")
    return checked


def check_parameters(candidate: dict, rules: dict, *,
                     proposal: dict,
                     labels: tuple,
                     trusted_resolvers: dict[str, Callable]) -> bool:
    """Fail closed when a requested field, resolver, value or evidence is missing.

    Trusted resolvers must read a trusted system, not parse model-authored output.
    The resolver gets a deep copy of the entire proposal; the trusted host must
    validate any untrusted lookup keys, subject and tenant in that resolver.
    """
    if not isinstance(candidate, dict) or set(candidate) != set(rules):
        return False
    for name, rule in rules.items():
        value = candidate[name]
        kind = rule["kind"]
        if kind == "exact":
            if _canon(value) != _canon(rule["value"]):
                return False
        elif kind == "one_of":
            if not any(_canon(value) == _canon(option) for option in rule["values"]):
                return False
        elif kind == "decimal_range":
            try:
                amount = _money(value)
                if not _money(rule["minimum"]) <= amount <= _money(rule["maximum"]):
                    return False
            except ValueError:
                return False
        elif kind == "trusted_lookup":
            resolver = trusted_resolvers.get(rule["resolver"])
            if resolver is None:
                return False
            try:
                authoritative = resolver(name, copy.deepcopy(proposal), tuple(labels))
            except Exception:
                return False
            if (not isinstance(authoritative, VerifiedParameter)
                    or authoritative.source_id != rule["source_id"]
                    or not isinstance(authoritative.source_version, str)
                    or not authoritative.source_version
                    or _canon(authoritative.value) != _canon(value)):
                return False
        else:
            return False
    return True


def validate_approval(source: str, reference: str) -> None:
    if (source not in _ALLOWED_APPROVALS or not isinstance(reference, str)
            or not reference.strip() or len(reference) > 256):
        raise ValueError("invalid_host_approval_provenance")
