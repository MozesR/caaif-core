"""CAAIF SDK v0.9 *experimental* independent context provider.

Loopback-only reference implementation. Authorization happens inside the provider
on every read; no shared module-level local state with the agent processes.
Not TLS / workload identity / durable storage / enterprise PDP.
"""
from __future__ import annotations

import copy
import hmac
import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_BODY = 1_048_576


def encoded(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"), sort_keys=True).encode("utf-8")


class ProviderError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code
        super().__init__(f"{status}:{code}")


@dataclass
class _Entry:
    owner: str
    ref: str
    version: str
    scope: str
    correlation_id: str
    value: dict
    grants: dict[str, list[str]]
    revoked: bool = False


class ContextProviderV09:
    """In-memory independent HTTP service with capability-specific token actors.

    Each reader receives only fields granted to their authenticated actor id.
    A new version makes the previous version unavailable; revocation takes
    effect for subsequent requests and doesn't erase copies already delivered.
    """

    def __init__(self, actors: dict[str, str], *,
                 authorize_read: Callable[[str, str, str, str, str], bool],
                 port: int = 0):
        if not isinstance(actors, dict) or not actors or any(
            not isinstance(name, str) or not name or not isinstance(secret, str) or len(secret) < 24
            for name, secret in actors.items()
        ) or len(set(actors.values())) != len(actors):
            raise ValueError("invalid_actor_credentials")
        if not callable(authorize_read):
            raise ValueError("provider_policy_required")
        self._authorize_read = authorize_read
        self._actors = dict(actors)
        self._contexts: dict[str, _Entry] = {}
        self._lock = threading.RLock()
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Do not print tokens, context or request details.

            def reply(self, status: int, obj: dict):
                wire = encoded(obj)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(wire)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(wire)

            def do_GET(self):
                if self.path == "/health":
                    return self.reply(200, {"status": "ok", "service": "caaif-context-provider-v09"})
                self.reply(404, {"error": "not_found"})

            def do_POST(self):
                if self.path not in ("/publish", "/read", "/revoke"):
                    return self.reply(404, {"error": "not_found"})
                auth = self.headers.get("Authorization", "")
                token = auth[7:] if auth.startswith("Bearer ") else ""
                actor = next((name for name, expected in provider._actors.items()
                              if hmac.compare_digest(token, expected)), None)
                if actor is None:
                    return self.reply(401, {"error": "unauthorized"})
                try:
                    length = self.headers.get("Content-Length", "")
                    if not length.isdigit() or not 0 < int(length) <= MAX_BODY:
                        raise ProviderError(400, "invalid_body_length")
                    data = json.loads(self.rfile.read(int(length)))
                    if not isinstance(data, dict):
                        raise ProviderError(400, "json_object_required")
                    with provider._lock:
                        result = provider._apply(self.path, actor, data)
                    self.reply(200, result)
                except ProviderError as e:
                    self.reply(e.status, {"error": e.code})
                except (ValueError, TypeError, json.JSONDecodeError):
                    self.reply(400, {"error": "invalid_payload"})
                except Exception:
                    self.reply(500, {"error": "internal_error"})

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread: threading.Thread | None = None

    def _apply(self, path: str, actor: str, p: dict):
        if path == "/publish":
            keys = {"ref", "version", "scope", "correlation_id", "value", "grants"}
            if set(p) != keys:
                raise ProviderError(400, "invalid_publish_fields")
            for k in ("ref", "version", "scope", "correlation_id"):
                if not isinstance(p[k], str) or not p[k] or len(p[k]) > 256:
                    raise ProviderError(400, "invalid_context_metadata")
            value, grants = p["value"], p["grants"]
            if not isinstance(value, dict) or not isinstance(grants, dict) or not grants:
                raise ProviderError(400, "invalid_context_permissions")
            if any(not isinstance(k, str) for k in value):
                raise ProviderError(400, "invalid_context_value")
            if any(recipient not in self._actors or not isinstance(fields, list)
                   or not fields or len(fields) != len(set(map(str, fields)))
                   or not all(isinstance(f, str) and f in value for f in fields)
                   for recipient, fields in grants.items()):
                raise ProviderError(400, "invalid_context_permissions")
            previous = self._contexts.get(p["ref"])
            if previous and previous.owner != actor:
                raise ProviderError(403, "not_context_owner")
            if previous and previous.revoked:
                raise ProviderError(409, "revoked_reference_cannot_update")
            if previous and previous.version == p["version"]:
                raise ProviderError(409, "immutable_context_version")
            if previous and (previous.scope != p["scope"] or
                             previous.correlation_id != p["correlation_id"]):
                raise ProviderError(403, "context_boundary_immutable")
            self._contexts[p["ref"]] = _Entry(
                owner=actor, ref=p["ref"], version=p["version"],
                scope=p["scope"], correlation_id=p["correlation_id"],
                value=copy.deepcopy(value), grants=copy.deepcopy(grants))
            return {"ref": p["ref"], "version": p["version"], "scope": p["scope"]}
        if path == "/read":
            if set(p) != {"ref", "version", "scope", "correlation_id"}:
                raise ProviderError(400, "invalid_read_fields")
            if any(not isinstance(v, str) or not v for v in p.values()):
                raise ProviderError(400, "invalid_read_fields")
            item = self._contexts.get(p["ref"])
            if item is None or item.revoked:
                raise ProviderError(403, "context_unavailable")
            if item.version != p["version"]:
                raise ProviderError(403, "context_version_conflict")
            if item.scope != p["scope"] or item.correlation_id != p["correlation_id"]:
                raise ProviderError(403, "context_boundary_denied")
            fields = item.grants.get(actor)
            # Publisher grants are necessary but NOT sufficient. A separate,
            # trusted provider-side policy is checked on *every* retrieval.
            try:
                authorized = self._authorize_read(actor, item.ref, item.version,
                                                  item.scope, item.correlation_id)
            except Exception:
                authorized = False
            if fields is None or authorized is not True:
                raise ProviderError(403, "context_reader_denied")
            selected = {key: item.value[key] for key in fields}
            return {"ref": item.ref, "version": item.version, "value": copy.deepcopy(selected)}
        if path == "/revoke":
            if set(p) != {"ref", "correlation_id"} or any(
                not isinstance(v, str) or not v for v in p.values()
            ):
                raise ProviderError(400, "invalid_revoke_fields")
            item = self._contexts.get(p["ref"])
            if item is None or item.owner != actor or item.correlation_id != p["correlation_id"]:
                raise ProviderError(403, "revoke_not_permitted")
            item.revoked = True
            return {"revoked": True}
        raise ProviderError(404, "not_found")

    def start(self):
        if self._thread is not None:
            raise RuntimeError("already_started")
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def serve_forever(self):
        self._server.serve_forever()

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()


class ProviderClientV09:
    """Endpoint client. Actor determined by server-side bearer token, not caller-supplied name."""

    def __init__(self, url: str, token: str):
        parts = urlsplit(url)
        if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parts.path not in ("", "/") or parts.username or parts.password
                or parts.fragment or parts.query or not isinstance(token, str) or len(token) < 24):
            raise ValueError("loopback_provider_required")
        self.url = url.rstrip("/")
        self.token = token
        self.calls = 0
        self.body_bytes = 0

    def post(self, path: str, data: dict) -> dict:
        if path not in ("/publish", "/read", "/revoke"):
            raise ValueError("unknown_endpoint")
        content = encoded(data)
        request = Request(self.url + path, content, {"Content-Type": "application/json",
                         "Authorization": "Bearer " + self.token}, method="POST")
        self.calls += 1
        self.body_bytes += len(content)
        try:
            with urlopen(request, timeout=5) as response:
                wire = response.read(MAX_BODY + 1)
                self.body_bytes += len(wire)
                if len(wire) > MAX_BODY:
                    raise ProviderError(502, "response_too_large")
                return json.loads(wire)
        except HTTPError as exc:
            wire = exc.read(MAX_BODY + 1)
            self.body_bytes += len(wire)
            try:
                code = json.loads(wire).get("error", "unknown_error")
            except (ValueError, AttributeError):
                code = "unknown_error"
            raise ProviderError(exc.code, code) from None

    def publish(self, *, ref: str, version: str, scope: str, correlation_id: str,
                value: dict, grants: dict[str, list[str]]) -> dict:
        return self.post("/publish", dict(ref=ref, version=version, scope=scope,
                                          correlation_id=correlation_id, value=value, grants=grants))

    def read(self, *, ref: str, version: str, scope: str, correlation_id: str) -> dict:
        return self.post("/read", dict(ref=ref, version=version, scope=scope,
                                       correlation_id=correlation_id))

    def revoke(self, *, ref: str, correlation_id: str) -> dict:
        return self.post("/revoke", {"ref": ref, "correlation_id": correlation_id})
