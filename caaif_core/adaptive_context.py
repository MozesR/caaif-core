"""CAAIF Core v0.6: conservative, framework-independent context-mode selection.

This is a *transport decision only*, not an authorization engine.
Caller must supply an independently authorized selection; reference storage,
versioning, and retrieval remain subject to the CAAIF Controller's policy.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ContextMode(str, Enum):
    INLINE_FULL = "inline_full"
    INLINE_SELECTED = "inline_selected"
    REFERENCE_SELECTED = "reference_selected"


class ContextPolicyDenied(ValueError):
    """Fail closed when no permitted exchange mode is available."""


def _size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), sort_keys=True,
                          ensure_ascii=False, allow_nan=False).encode("utf-8"))


@dataclass(frozen=True)
class ContextDecision:
    mode: ContextMode
    full_bytes: int
    selected_bytes: int
    reason: str


@dataclass(frozen=True)
class AdaptiveContextPolicy:
    """Choose the smallest safe inline payload, otherwise use a scoped ref.

    max_inline_bytes: local policy limit *for context data*, not whole request.
    min_selection_savings: overhead/complexity preference for small messages;
    it is not a measured HTTP cost model. Default authorization denies full
    context even when it is small; allowing it requires explicit opt-in.
    """
    max_inline_bytes: int = 1024
    min_selection_savings: int = 64

    def __post_init__(self):
        if (type(self.max_inline_bytes) is not int or self.max_inline_bytes < 1
                or type(self.min_selection_savings) is not int or self.min_selection_savings < 0):
            raise ValueError("invalid_policy_threshold")

    def choose(self, full: Any, selected: Any, *,
               full_authorized: bool = False,
               selected_inline_authorized: bool = True,
               reference_available: bool = True,
               reference_required: bool = False) -> ContextDecision:
        # The selector is outside this module; it MUST be trusted/authorized.
        # A reference decision does not itself create or authorize a reference.
        fb, sb = _size(full), _size(selected)
        if reference_required:
            if not reference_available:
                raise ContextPolicyDenied("reference_required_unavailable")
            return ContextDecision(ContextMode.REFERENCE_SELECTED, fb, sb,
                                   "reference_required_by_context_policy")

        if selected_inline_authorized and sb <= self.max_inline_bytes:
            if (full_authorized and fb <= self.max_inline_bytes
                    and fb - sb < self.min_selection_savings):
                return ContextDecision(ContextMode.INLINE_FULL, fb, sb,
                                       "small_authorized_context")
            return ContextDecision(ContextMode.INLINE_SELECTED, fb, sb,
                                   "minimal_authorized_inline_context")

        if full_authorized and fb <= self.max_inline_bytes:
            return ContextDecision(ContextMode.INLINE_FULL, fb, sb,
                                   "authorized_full_context_only")

        if reference_available:
            return ContextDecision(ContextMode.REFERENCE_SELECTED, fb, sb,
                                   "inline_forbidden_or_over_limit")
        raise ContextPolicyDenied("no_authorized_context_exchange")
