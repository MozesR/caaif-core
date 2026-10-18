"""CAAIF SDK v0.7 research component: bounded, re-authorized versioned context cache.

This cache does NOT confer access rights. Callers must supply a trusted, independently
implemented authorization function. Never let an untrusted agent choose it.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable


class ContextCacheDenied(ValueError):
    """Denied/stale/invalid context is never served from cache."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def string_splice(old: str, new: str) -> dict:
    """Create a compact replacement for one string, counting Python characters."""
    if not isinstance(old, str) or not isinstance(new, str):
        raise TypeError("strings_required")
    front = 0
    while front < min(len(old), len(new)) and old[front] == new[front]:
        front += 1
    back = 0
    while (back < len(old) - front and back < len(new) - front
           and old[len(old) - back - 1] == new[len(new) - back - 1]):
        back += 1
    return {"prefix": front, "delete": len(old) - front - back,
            "insert": new[front:len(new)-back if back else len(new)]}


def apply_splice(old: str, splice: dict) -> str:
    if (not isinstance(old, str) or not isinstance(splice, dict)
            or set(splice) != {"prefix", "delete", "insert"}):
        raise ContextCacheDenied("invalid_delta")
    p, d, ins = splice["prefix"], splice["delete"], splice["insert"]
    if (type(p) is not int or type(d) is not int or not isinstance(ins, str)
            or p < 0 or d < 0 or p + d > len(old)):
        raise ContextCacheDenied("invalid_delta")
    return old[:p] + ins + old[p+d:]


class VersionedContextCache:
    """Cache keys bind recipient, ref, scope, version and correlation.

    ``authorize(recipient, ref, version, scope, correlation_id)`` is a TRUSTED
    Controller authorization callback evaluated on *every* cache read or write.
    A returned True is necessary, not sufficient: version and digest also bind.
    """

    def __init__(self, authorize: Callable[..., bool], *, max_entries=64,
                 max_value_bytes=1048576, ttl_seconds=120.0,
                 clock: Callable[[], float] = time.monotonic):
        if not callable(authorize) or not callable(clock) or type(max_entries) is not int or max_entries < 1:
            raise ValueError("invalid_cache_configuration")
        if (type(max_value_bytes) is not int or max_value_bytes < 1
                or type(ttl_seconds) not in (int, float) or ttl_seconds <= 0):
            raise ValueError("invalid_cache_configuration")
        self.authorize = authorize
        self.max_entries = max_entries
        self.max_value_bytes = max_value_bytes
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._items: OrderedDict[tuple, tuple] = OrderedDict()

    def _key(self, recipient: str, ref: str, version: str, scope: str,
             correlation_id: str):
        parts = (recipient, ref, version, scope, correlation_id)
        if not all(isinstance(x, str) and x for x in parts):
            raise ContextCacheDenied("invalid_context_identity")
        return parts

    def _permit(self, key):
        try:
            permitted = self.authorize(*key)
        except Exception as exc:
            raise ContextCacheDenied("authorization_unavailable") from exc
        if permitted is not True:
            raise ContextCacheDenied("context_access_denied")

    def get(self, recipient, ref, version, scope, correlation_id):
        key = self._key(recipient, ref, version, scope, correlation_id)
        self._permit(key)
        entry = self._items.get(key)
        if entry is None:
            return None
        value, expiration = entry
        if self.clock() >= expiration:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return copy.deepcopy(value)

    def store(self, recipient, ref, version, scope, correlation_id, value):
        key = self._key(recipient, ref, version, scope, correlation_id)
        self._permit(key)
        if len(canonical(value)) > self.max_value_bytes:
            raise ContextCacheDenied("cache_value_too_large")
        self._items[key] = (copy.deepcopy(value), self.clock()+self.ttl_seconds)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def delta(self, recipient, ref, base_version, version, scope, correlation_id, patch):
        """Apply a Controller-authorized version transition, atomically in memory.

        The trusted Controller MUST validate patch content before dispatch;
        hash matching detects accidental mismatches but is not authentication.
        The old base may have been superseded; only the target needs current permission.
        """
        target = self._key(recipient, ref, version, scope, correlation_id)
        base = self._key(recipient, ref, base_version, scope, correlation_id)
        self._permit(target)
        if version == base_version or not isinstance(patch, dict) or set(patch) != {"changes", "digest"}:
            raise ContextCacheDenied("invalid_delta")
        if (not isinstance(patch["changes"], dict) or not isinstance(patch["digest"], str)
                or len(patch["digest"]) != 64):
            raise ContextCacheDenied("invalid_delta")
        entry = self._items.get(base)
        if entry is None or self.clock() >= entry[1]:
            raise ContextCacheDenied("cache_base_missing")
        value = copy.deepcopy(entry[0])
        if not isinstance(value, dict) or any(k not in value or not isinstance(value[k], str)
                                                 for k in patch["changes"]):
            raise ContextCacheDenied("invalid_delta_base")
        for field, change in patch["changes"].items():
            value[field] = apply_splice(value[field], change)
        if fingerprint(value) != patch["digest"]:
            raise ContextCacheDenied("delta_digest_mismatch")
        self.store(*target, value)
        self._items.pop(base, None)
        return copy.deepcopy(value)

    def invalidate(self, *, recipient=None, ref=None, correlation_id=None):
        for key in list(self._items):
            if ((recipient is None or recipient == key[0]) and (ref is None or ref == key[1])
                    and (correlation_id is None or correlation_id == key[4])):
                self._items.pop(key, None)
