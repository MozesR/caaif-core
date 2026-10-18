"""CAAIF v0.2 loopback HTTP adapter: prototype, NOT production network security.

Existing LocalController remains the one authority over contracts/decisions/context.
A recipient worker runs in another process, sees only a request with references,
and resolves approved references over a short-lived callback capability.
No LLM, persistence, retries, service discovery or A2A implementation.
"""
from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_BODY = 65536
MAX_CONTEXT_BODY = 1048576
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _safe_loopback(url: str, path: str) -> str:
    parts = urlsplit(url)
    if (parts.scheme != "http" or parts.hostname not in LOOPBACK or
            parts.username is not None or parts.password is not None or
            parts.query or parts.fragment or parts.path not in ("", "/")):
        raise ValueError("loopback_http_url_required")
    return url.rstrip("/") + path


def _json(data: Any) -> bytes:
    return json.dumps(data, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _read_json(handler: BaseHTTPRequestHandler, limit: int = MAX_BODY) -> dict:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None or not raw_length.isdigit() or not 0 < int(raw_length) <= limit:
        raise ValueError("invalid_content_length")
    obj = json.loads(handler.rfile.read(int(raw_length)))
    if not isinstance(obj, dict):
        raise ValueError("expected_json_object")
    return obj


def _reply(handler: BaseHTTPRequestHandler, code: int, data: dict):
    body = _json(data)
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send(url: str, body: dict, token: str, *, timeout: float = 5.0) -> dict:
    req = Request(url, _json(body), {"Content-Type": "application/json",
                                    "Authorization": "Bearer " + token}, method="POST")
    with urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read(MAX_CONTEXT_BODY + 1))
    if not isinstance(data, dict):
        raise ValueError("invalid_remote_response")
    return data


class ContextRelay:
    """Per-dispatch context capabilities, bound to a LocalController _ContextView.

    MUST run only on loopback. Context rights are still independently checked
    by _ContextView.resolve before exposing a JSON value to a remote recipient.
    """

    def __init__(self, *, ttl: float = 30.0):
        self._ttl = ttl
        self._lock = threading.RLock()
        self._tickets: dict[str, tuple[float, Any]] = {}
        relay = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return  # Do not log credentials, refs or request payloads.

            def do_POST(self):
                if self.path != "/context/resolve":
                    return _reply(self, 404, {"error": "not_found"})
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return _reply(self, 401, {"error": "unauthorized"})
                secret = auth[7:]
                with relay._lock:
                    entry = next(((k, v) for k, v in relay._tickets.items()
                                  if hmac.compare_digest(k, secret)), None)
                if entry is None or entry[1][0] <= time.monotonic():
                    return _reply(self, 401, {"error": "unauthorized"})
                try:
                    body = _read_json(self)
                    if set(body) != {"ref"} or not isinstance(body["ref"], str):
                        raise ValueError("invalid_context_request")
                    value = entry[1][1].resolve(body["ref"])
                    if len(_json(value)) > MAX_CONTEXT_BODY:
                        raise ValueError("context_too_large")
                    return _reply(self, 200, {"value": value})
                except (KeyError, TypeError, ValueError) as exc:
                    return _reply(self, 400, {"error": type(exc).__name__})
                except Exception:
                    return _reply(self, 403, {"error": "context_denied"})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread: threading.Thread | None = None
        self.url = f"http://127.0.0.1:{self._server.server_port}"

    def start(self):
        if self._thread is not None:
            raise RuntimeError("relay_already_started")
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    @contextmanager
    def ticket(self, context):
        secret = secrets.token_urlsafe(32)
        with self._lock:
            self._tickets[secret] = (time.monotonic() + self._ttl, context)
        try:
            yield secret
        finally:
            with self._lock:
                self._tickets.pop(secret, None)

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()


class RemoteContext:
    """Recipient-side authorized context accessor, not a local context cache."""

    def __init__(self, relay_url: str, ticket: str):
        self._url = _safe_loopback(relay_url, "/context/resolve")
        if not ticket:
            raise ValueError("missing_context_ticket")
        self._ticket = ticket

    def resolve(self, ref: str) -> Any:
        obj = _send(self._url, {"ref": ref}, self._ticket)
        if set(obj) != {"value"}:
            raise ValueError("invalid_context_response")
        return obj["value"]


class HTTPTransport:
    """Calls a remote, loopback worker. The caller is still bound by LocalController."""

    def __init__(self, *, url: str, recipient_id: str, auth_token: str,
                 relay: ContextRelay, timeout: float = 10.0):
        self._url = _safe_loopback(url, "/invoke")
        if not recipient_id or len(auth_token) < 16:
            raise ValueError("invalid_worker_identity")
        self._recipient_id = recipient_id
        self._token = auth_token
        self._relay = relay
        self._timeout = timeout

    def __call__(self, request: dict, context: Any) -> dict:
        if request.get("recipient_id") != self._recipient_id:
            raise ValueError("recipient_identity_mismatch")
        with self._relay.ticket(context) as ticket:
            obj = _send(self._url, {"request": request, "context_url": self._relay.url,
                                    "context_ticket": ticket}, self._token, timeout=self._timeout)
        if set(obj) != {"output"} or not isinstance(obj["output"], dict):
            raise ValueError("remote_agent_invalid_result")
        return obj["output"]


class AgentHTTPServer:
    """Independent recipient process. Only an authorized Controller can invoke it.

    Loopback-only demonstration; shared bearer credentials are NOT workload
    identity and must not be used over an untrusted network.
    """

    def __init__(self, *, agent_id: str, auth_token: str,
                 handler: Callable[[dict, RemoteContext], dict], port: int = 0):
        if not agent_id or len(auth_token) < 16 or not callable(handler):
            raise ValueError("invalid_worker_config")
        worker_id, secret, fn = agent_id, auth_token, handler

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_GET(self):
                if self.path == "/health":
                    return _reply(self, 200, {"status": "ok"})
                return _reply(self, 404, {"error": "not_found"})

            def do_POST(self):
                if self.path != "/invoke":
                    return _reply(self, 404, {"error": "not_found"})
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
                    return _reply(self, 401, {"error": "unauthorized"})
                try:
                    body = _read_json(self)
                    if set(body) != {"request", "context_url", "context_ticket"}:
                        raise ValueError("invalid_envelope")
                    request = body["request"]
                    if not isinstance(request, dict) or request.get("recipient_id") != worker_id:
                        return _reply(self, 403, {"error": "recipient_identity_mismatch"})
                    context = RemoteContext(body["context_url"], body["context_ticket"])
                    output = fn(request, context)
                    if not isinstance(output, dict) or len(_json(output)) > MAX_CONTEXT_BODY:
                        raise ValueError("invalid_agent_output")
                    return _reply(self, 200, {"output": output})
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    return _reply(self, 400, {"error": "invalid_request"})
                except HTTPError:
                    return _reply(self, 403, {"error": "context_denied"})
                except (URLError, TimeoutError):
                    return _reply(self, 503, {"error": "context_unavailable"})
                except Exception:
                    return _reply(self, 500, {"error": "handler_failed"})

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def serve_forever(self):
        self._server.serve_forever()

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()
