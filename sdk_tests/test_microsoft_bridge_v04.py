"""Core v0.4 Microsoft-response bridge tests; no third-party package required."""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from caaif_core.local import Denied
from caaif_core.microsoft_bridge import microsoft_task_adapter


class Context:
    def __init__(self, value):
        self.value = value
        self.refs = []

    def resolve(self, ref):
        self.refs.append(ref)
        if ref != "ctx:allowed":
            raise Denied("context_reader_denied")
        return self.value


class SyntheticAsyncAgent:
    def __init__(self, text=None):
        self.text = text or json.dumps({"topic": "topic", "points": ["A", "B"]})
        self.received = []

    async def run(self, prompt):
        self.received.append(prompt)
        return SimpleNamespace(text=self.text)


class Tests(unittest.TestCase):
    def req(self, ref="ctx:allowed"):
        return {"context_refs": [{"ref": ref}]}

    def test_only_authorized_topic_reaches_agent(self):
        agent = SyntheticAsyncAgent()
        context = Context({"topic": "topic", "private": "SECRET"})
        result = microsoft_task_adapter(agent)(self.req(), context)
        self.assertEqual(agent.received, ["topic"])
        self.assertEqual(context.refs, ["ctx:allowed"])
        self.assertEqual(result["points"], ["A", "B"])

    def test_denied_context_never_reaches_agent(self):
        agent = SyntheticAsyncAgent()
        with self.assertRaises(Denied):
            microsoft_task_adapter(agent)(self.req("ctx:unapproved"), Context({"topic": "topic"}))
        self.assertEqual(agent.received, [])

    def test_ref_required(self):
        with self.assertRaises(ValueError):
            microsoft_task_adapter(SyntheticAsyncAgent())({"context_refs": []}, Context({"topic": "topic"}))

    def test_empty_topic_rejected(self):
        with self.assertRaises(ValueError):
            microsoft_task_adapter(SyntheticAsyncAgent())(self.req(), Context({"topic": "  "}))

    def test_invalid_response_json_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_json"):
            microsoft_task_adapter(SyntheticAsyncAgent("not json"))(self.req(), Context({"topic": "topic"}))

    def test_extra_unexpected_response_fields_rejected(self):
        data=json.dumps({"topic":"topic","points":["A"],"extra":"oops"})
        with self.assertRaisesRegex(ValueError, "unexpected_agent_output_shape"):
            microsoft_task_adapter(SyntheticAsyncAgent(data))(self.req(), Context({"topic": "topic"}))

    def test_run_requires_worker_thread(self):
        adapter = microsoft_task_adapter(SyntheticAsyncAgent())
        async def test():
            with self.assertRaisesRegex(RuntimeError,"worker_thread"):
                adapter(self.req(), Context({"topic":"topic"}))
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
