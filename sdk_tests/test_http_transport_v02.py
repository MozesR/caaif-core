"""Loopback HTTP adapter integration and negative security tests."""
import json
import secrets
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core.local import LocalController, Denied
from caaif_core.transport import InProcessTransport
from caaif_core.http_transport import AgentHTTPServer, ContextRelay, HTTPTransport, RemoteContext, _send


def fixture():
    contract = {"spec_version": "1.0.0-draft.2", "contract_id": "general.read", "version": "1",
                "caller_id": "agent.a", "recipient_id": "agent.b", "capability": "read",
                "context_policy": {"allowed_scopes": ["project.data"], "max_inline_bytes": 1024,
                                   "max_refs": 2}, "effect": "read_only",
                "limits": {"ttl_seconds": 60, "max_request_bytes": 8192}}
    core = LocalController(contracts=[contract], policy=lambda _r, _c: True)
    return core


class Tests(unittest.TestCase):
    def setUp(self):
        self.relay = ContextRelay().start()
        self.token = secrets.token_urlsafe(32)
        self.worker = AgentHTTPServer(agent_id="agent.b", auth_token=self.token,
                                      handler=lambda r,c:{"found":c.resolve(r["context_refs"][0]["ref"])})
        self.worker.start()
        self.core = fixture()
        self.a = self.core.attach("agent.a", lambda *_: {})
        self.b = self.core.attach("agent.b", HTTPTransport(url=self.worker.url,
                                         recipient_id="agent.b", auth_token=self.token, relay=self.relay))
        self.ref = self.core.put_context(self.a, ref="ctx:sample", version="v1",
                                          scope="project.data", value={"hello":"world"},
                                          readers={"agent.b"}, correlation_id="sample")

    def tearDown(self):
        self.worker.close()
        self.relay.close()

    def request(self):
        return self.core.new_request(self.a, contract_id="general.read",
                                     correlation_id="sample", context_refs=[self.ref])

    def test_remote_agent_resolves_context(self):
        result = self.core.dispatch(self.a, self.request())
        self.assertEqual(result["output"]["found"], {"hello": "world"})
        self.assertEqual(result["used_context_versions"], {"ctx:sample":"v1"})

    def test_context_not_included_inline(self):
        req = self.request()
        self.assertNotIn("world", json.dumps(req))
        self.assertEqual(len(req["context_refs"]), 1)

    def test_another_agent_cannot_impersonate_caller(self):
        req = self.request()
        with self.assertRaises(Denied) as e:
            self.core.dispatch(self.b, req)
        self.assertEqual(e.exception.code, "contract_or_identity_mismatch")

    def test_worker_rejects_wrong_bearer(self):
        with self.assertRaises(HTTPError) as exc:
            _send(self.worker.url + "/invoke", {"request": self.request(),
                "context_url": self.relay.url, "context_ticket": "foo"}, "wrong")
        self.assertEqual(exc.exception.code, 401)

    def test_worker_rejects_wrong_recipient_even_with_bearer(self):
        req = self.request()
        req["recipient_id"] = "agent.c"
        with self.assertRaises(HTTPError) as exc:
            _send(self.worker.url + "/invoke", {"request": req,
                "context_url": self.relay.url, "context_ticket": "foo"}, self.token)
        self.assertEqual(exc.exception.code, 403)

    def test_invalid_context_ref_fails_closed(self):
        ref = dict(self.ref, ref="ctx:unknown")
        req = self.core.new_request(self.a, contract_id="general.read",
                                    correlation_id="sample", context_refs=[ref])
        with self.assertRaises(Denied):
            self.core.dispatch(self.a, req)

    def test_revoked_context_fails_closed(self):
        self.core.revoke_context(self.ref["ref"])
        with self.assertRaises(Denied) as exc:
            self.core.dispatch(self.a, self.request())
        self.assertEqual(exc.exception.code, "context_unavailable")

    def test_stale_context_ticket_cannot_be_used(self):
        class Context:
            def resolve(self, ref):
                return "foo"
        with self.relay.ticket(Context()) as ticket:
            self.assertEqual(RemoteContext(self.relay.url, ticket).resolve("x"), "foo")
        with self.assertRaises(HTTPError) as exc:
            RemoteContext(self.relay.url, ticket).resolve("x")
        self.assertEqual(exc.exception.code, 401)

    def test_external_context_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            RemoteContext("http://example.org", "ticket")

    def test_local_adapter_keeps_existing_semantics(self):
        adapter = InProcessTransport(lambda request,context: {"worked":True})
        self.assertEqual(adapter({},None), {"worked":True})


if __name__ == "__main__":
    unittest.main()
