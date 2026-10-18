"""Framework bridge conformance tests without vendor dependencies."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core.framework_adapters import CallableAgentAdapter, GraphInvokeAdapter, AsyncRunAdapter
from caaif_core.local import LocalController, Denied
from examples.sdk_framework_adapter_demo import demo


class StubContext:
    def resolve(self, ref):
        if ref != "approved":
            raise Denied("undeclared_context_ref")
        return {"topic": "test"}


class StubGraph:
    def invoke(self, state):
        return {"answer": state["text"].upper()}


class StubAsyncAgent:
    async def run(self, msg):
        return type("Response", (), {"text": msg.upper()})()


class Tests(unittest.TestCase):
    def test_callable_adapter(self):
        handler = CallableAgentAdapter(lambda r,c: {"ok":True})
        self.assertEqual(handler({}, None), {"ok": True})

    def test_callable_rejects_non_dict_output(self):
        with self.assertRaises(TypeError):
            CallableAgentAdapter(lambda _r,_c: "bad")({}, None)

    def test_callable_rejects_non_json_output(self):
        with self.assertRaises(ValueError):
            CallableAgentAdapter(lambda _r,_c: {"bad": float("nan")})({}, None)

    def test_graph_invokes_mapped_state_only(self):
        seen = []
        def map_input(request, context):
            seen.append(request["intent"])
            return {"text":context.resolve("approved")["topic"]}
        adapter=GraphInvokeAdapter(StubGraph(), to_state=map_input,
              from_state=lambda output, _r: output)
        self.assertEqual(adapter({"intent":"analyze"}, StubContext()), {"answer":"TEST"})
        self.assertEqual(seen, ["analyze"])

    def test_graph_requires_graph_method(self):
        with self.assertRaises(TypeError):
            GraphInvokeAdapter(object(), to_state=lambda _r,_c:{}, from_state=lambda o,r:o)

    def test_graph_context_raises_on_denial(self):
        adapter=GraphInvokeAdapter(StubGraph(), to_state=lambda _r,c:{"text":c.resolve("forbidden")},
                                   from_state=lambda o,r:o)
        with self.assertRaises(Denied):
            adapter({}, StubContext())

    def test_async_agent_maps_text_result(self):
        adapter=AsyncRunAdapter(StubAsyncAgent(), to_input=lambda r,c:"hello",
                                from_response=lambda response, _r:{"message":response.text})
        self.assertEqual(adapter({},None), {"message":"HELLO"})

    def test_async_agent_rejects_sync_run(self):
        class SyncAgent:
            def run(self,_): return {"value": 1}
        adapter=AsyncRunAdapter(SyncAgent(), to_input=lambda r,c:"test", from_response=lambda r,q:r)
        with self.assertRaises(TypeError):
            adapter({},None)

    def test_async_agent_rejects_existing_event_loop(self):
        adapter=AsyncRunAdapter(StubAsyncAgent(),to_input=lambda r,c:"hello",
                               from_response=lambda r,q:{"message":r.text})
        async def invoke():
            with self.assertRaisesRegex(RuntimeError,"worker_thread"):
                adapter({},None)
        asyncio.run(invoke())

    def test_three_role_integration(self):
        core=demo()
        self.assertEqual(sum(e["event"]=="completed" for e in core.events),4)
        self.assertEqual(sum(e["event"]=="context_resolved" for e in core.events),4)

    def test_direct_conversation_to_task_forbidden(self):
        profile = json.loads((ROOT / "examples/three-agent/profile.json").read_text())
        contract = json.loads((ROOT / "examples/three-agent/contracts/reasoning_to_task.json").read_text())
        contract["caller_id"] = "demo.agent.conversational"
        contract["profile_binding"]["caller_role"] = "conversational"
        with self.assertRaises(ValueError):
            LocalController(profile=profile,contracts=[contract],policy=lambda r,c:True)


if __name__ == "__main__":
    unittest.main()
