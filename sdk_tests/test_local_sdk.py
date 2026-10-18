"""Runtime tests of the CAAIF Local Profile research SDK (not Guarded conformance)."""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core import AgentHandle, Denied, LocalController  # noqa

EXAMPLES = ROOT / "examples" / "three-agent"


def fixture(filename):
    return json.loads((EXAMPLES / filename).read_text())


class LocalTests(unittest.TestCase):
    def setUp(self):
        profile = fixture("profile.json")
        contracts = [json.loads(f.read_text()) for f in sorted((EXAMPLES / "contracts").glob("*.json"))]
        self.executions = 0

        def handler(request, context):
            self.executions += 1
            return {"value": "ok", "context": [context.resolve(r["ref"]) for r in request["context_refs"]]}

        self.core = LocalController(profile=profile, contracts=contracts,
                                    policy=lambda r, c: True, effect_policy=lambda r, c: True)
        self.c = self.core.attach("demo.agent.conversational", handler)
        self.r = self.core.attach("demo.agent.reasoning", handler)
        self.t = self.core.attach("demo.agent.task", handler)
        self.corr = "demo-fixture-01"
        self.intent = self.core.put_context(self.c, ref="ctx:demo/int", version="v1", scope="session.intent",
                                             value={"topic": "notes"}, readers={self.r.agent_id}, correlation_id=self.corr)
        self.instructions = self.core.put_context(self.r, ref="ctx:demo/instructions", version="v1",
                                                   scope="workspace.instructions", value={"topic": "notes"},
                                                   readers={self.t.agent_id}, correlation_id=self.corr)

    def request_intent(self):
        return self.core.new_request(self.c, contract_id="demo.three-agent.intent.v1",
                                     correlation_id=self.corr, context_refs=[self.intent])

    def request_task(self, **kw):
        decision = kw.pop("decision_ref", None)
        if decision is None:
            decision = self.core.issue_decision(self.r, correlation_id=self.corr,
                                                 contract_id="demo.three-agent.execute.v1",
                                                 recipient_id=self.t.agent_id, capability="task.execute", authorized=True)
        return self.core.new_request(self.r, contract_id="demo.three-agent.execute.v1",
                                     correlation_id=self.corr, context_refs=[self.instructions],
                                     decision_ref=decision, idempotency_key="demo-123", data={"operation": "create_outline"}, **kw)

    def deny(self, code, fn):
        with self.assertRaises(Denied) as cm:
            fn()
        self.assertEqual(cm.exception.code, code)

    def test_intent_allowed_and_context_selective(self):
        output = self.core.dispatch(self.c, self.request_intent())
        self.assertEqual(output["status"], "completed")
        self.assertEqual(output["used_context_versions"], {"ctx:demo/int": "v1"})

    def test_effect_requires_trusted_decision(self):
        req = self.request_task()
        del req["decision_ref"]
        self.deny("reasoning_decision_invalid", lambda: self.core.dispatch(self.r, req))

    def test_effect_accepts_matching_decision(self):
        self.assertEqual(self.core.dispatch(self.r, self.request_task())["status"], "completed")

    def test_task_direct_bypass_denied(self):
        req = self.request_task()
        req["caller_id"] = self.c.agent_id
        self.deny("contract_or_identity_mismatch", lambda: self.core.dispatch(self.c, req))

    def test_fake_principal_denied(self):
        self.deny("caller_not_bound", lambda: self.core.dispatch(AgentHandle(self.c.agent_id), self.request_intent()))

    def test_caller_spoof_denied(self):
        req = self.request_intent()
        req["caller_id"] = self.r.agent_id
        self.deny("contract_or_identity_mismatch", lambda: self.core.dispatch(self.c, req))

    def test_wrong_context_scope_denied(self):
        req = self.request_intent()
        req["context_refs"][0]["scope"] = "workspace.secret"
        self.deny("context_scope_denied", lambda: self.core.dispatch(self.c, req))

    def test_context_version_change_denied(self):
        req = self.request_intent()
        self.core.put_context(self.c, ref="ctx:demo/int", version="v2", scope="session.intent",
                              value={"topic": "revised"}, readers={self.r.agent_id}, correlation_id=self.corr)
        self.deny("context_version_conflict", lambda: self.core.dispatch(self.c, req))

    def test_context_revocation_denied(self):
        self.core.revoke_context("ctx:demo/int")
        self.deny("context_unavailable", lambda: self.core.dispatch(self.c, self.request_intent()))

    def test_unapproved_context_reader_denied(self):
        self.core.put_context(self.c, ref="ctx:demo/int", version="v2", scope="session.intent",
                              value={"topic": "private"}, readers={self.c.agent_id}, correlation_id=self.corr)
        req = self.request_intent()
        req["context_refs"] = [{"ref": "ctx:demo/int", "version": "v2", "scope": "session.intent"}]
        self.deny("context_reader_denied", lambda: self.core.dispatch(self.c, req))

    def test_duplicate_request_id_is_cached(self):
        req = self.request_task()
        a = self.core.dispatch(self.r, req)
        b = self.core.dispatch(self.r, req)
        self.assertEqual(a, b)
        self.assertEqual(self.executions, 1)

    def test_request_id_conflict_denied(self):
        req = self.request_intent()
        self.core.dispatch(self.c, req)
        changed = copy.deepcopy(req)
        changed["input"] = {"something": "different"}
        self.deny("request_id_conflict", lambda: self.core.dispatch(self.c, changed))

    def test_effect_idempotency_key_repeat_new_request_blocked(self):
        self.core.dispatch(self.r, self.request_task())
        self.deny("effect_already_reserved", lambda: self.core.dispatch(self.r, self.request_task()))

    def test_effect_policy_deny(self):
        core = LocalController(profile=fixture("profile.json"),
                               contracts=[json.loads(f.read_text()) for f in (EXAMPLES / "contracts").glob("*.json")],
                               policy=lambda r, c: True, effect_policy=lambda r, c: False)
        r = core.attach("demo.agent.reasoning", lambda r, c: {"ok": True})
        core.attach("demo.agent.task", lambda r, c: {"ok": True})
        dec = core.issue_decision(r, correlation_id="demo-1", contract_id="demo.three-agent.execute.v1",
                                  recipient_id="demo.agent.task", capability="task.execute", authorized=True)
        req = core.new_request(r, contract_id="demo.three-agent.execute.v1", correlation_id="demo-1",
                                decision_ref=dec, idempotency_key="effect-1")
        self.deny("effect_policy_denied", lambda: core.dispatch(r, req))

    def test_failure_leaves_uncertain_and_disallows_retry(self):
        self.core._handlers[self.t.agent_id] = lambda r,c: (_ for _ in ()).throw(RuntimeError("uncertain"))
        req = self.request_task()
        with self.assertRaises(RuntimeError):
            self.core.dispatch(self.r, req)
        self.deny("outcome_unknown", lambda: self.core.dispatch(self.r, req))

    def test_revoke_contract(self):
        self.core.revoke_contract("demo.three-agent.intent.v1", "1")
        self.deny("unknown_or_revoked_contract", lambda: self.core.dispatch(self.c, self.request_intent()))

    def test_audit_does_not_include_payload(self):
        req = self.request_intent()
        req["input"]["secret"] = "SENSITIVE_VALUE"
        self.core.dispatch(self.c, req)
        self.assertNotIn("SENSITIVE_VALUE", json.dumps(self.core.events))


if __name__ == "__main__":
    unittest.main()

class CoreOnlyTests(unittest.TestCase):
    def test_unprofiled_two_agent_operation(self):
        contract = {"spec_version": "1.0.0-draft.2", "contract_id": "generic.read.v1", "version": "1",
                    "caller_id": "agent.one", "recipient_id": "agent.two", "capability": "read",
                    "context_policy": {"allowed_scopes": ["project.notes"], "max_inline_bytes": 1024, "max_refs": 1},
                    "effect": "read_only", "limits": {"ttl_seconds": 60, "max_request_bytes": 8192}}
        core = LocalController(contracts=[contract], policy=lambda r, c: True)
        a = core.attach("agent.one", lambda r,ctx:{"reply":"not used"})
        b = core.attach("agent.two", lambda r,ctx:{"reply":ctx.resolve("ctx:note")})
        ref = core.put_context(a, ref="ctx:note", version="v1", scope="project.notes",
                               value="hello", readers={b.agent_id}, correlation_id="demo-2")
        request = core.new_request(a, contract_id="generic.read.v1", correlation_id="demo-2", context_refs=[ref])
        self.assertEqual(core.dispatch(a,request)["output"]["reply"], "hello")

    def test_unprofiled_effect_with_independent_policy(self):
        contract = {"spec_version": "1.0.0-draft.2", "contract_id": "generic.write.v1", "version": "1",
                    "caller_id": "agent.one", "recipient_id": "agent.two", "capability": "write",
                    "context_policy": {"allowed_scopes": [], "max_inline_bytes": 1024, "max_refs": 0},
                    "effect": "effectful", "limits": {"ttl_seconds": 60, "max_request_bytes": 8192}}
        core = LocalController(contracts=[contract], policy=lambda r, c: True,
                               effect_policy=lambda r, c: r["input"].get("operation") == "write")
        a = core.attach("agent.one", lambda r,ctx:{})
        core.attach("agent.two",lambda r,ctx:{"written":True})
        request=core.new_request(a, contract_id="generic.write.v1", correlation_id="c",
                                 data={"operation":"write"}, idempotency_key="effect-12")
        self.assertEqual(core.dispatch(a,request)["output"]["written"],True)
