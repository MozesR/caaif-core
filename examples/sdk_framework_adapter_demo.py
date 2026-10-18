"""CAAIF v0.3: SDK bridges across *different Python agent interfaces*.

This zero-dependency smoke demo uses a graph-shaped test double and an async
run-shaped test double. They are not LangGraph or Microsoft Agent Framework.
See sdk_langgraph_interop_demo.py for a demonstration with actual LangGraph.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core import LocalController
from caaif_core.framework_adapters import CallableAgentAdapter, GraphInvokeAdapter, AsyncRunAdapter

PROFILE = ROOT / "examples" / "three-agent"


class GraphShapedReasoning:
    """A graph API test double, NOT the LangGraph package."""
    def invoke(self, state):
        if state["capability"] == "intent.assess":
            return {"source_topic": state["context"]["topic"], "authorizes_outline": True}
        if state["capability"] == "task.report":
            return {"summary_points": state["context"]["points"]}
        raise ValueError("unknown_capability")


class AsyncShapedTask:
    """An async agent API test double, NOT Microsoft Agent Framework."""
    async def run(self, instructions):
        return {"points": ["What it is", "How it works", "Why it matters"],
                "topic": instructions["topic"]}


def demo(*, reasoning_graph=None):
    profile = json.loads((PROFILE / "profile.json").read_text())
    contracts = [json.loads(p.read_text()) for p in (PROFILE / "contracts").glob("*.json")]
    core = LocalController(profile=profile, contracts=contracts,
        policy=lambda req, _contract: req["correlation_id"].startswith("demo-"),
        effect_policy=lambda req, _contract: req["input"].get("operation") == "create_outline")

    conv = core.attach("demo.agent.conversational", CallableAgentAdapter(
        lambda req, ctx: {"message": "Here is your outline: " + "; ".join(
            ctx.resolve(req["context_refs"][0]["ref"])["points"])}))
    reason = core.attach("demo.agent.reasoning", GraphInvokeAdapter(
        reasoning_graph if reasoning_graph is not None else GraphShapedReasoning(),
        to_state=lambda req, ctx: {"capability": req["capability"],
            "context": ctx.resolve(req["context_refs"][0]["ref"])},
        from_state=lambda output, req: (
            {"source_topic": output["source_topic"], "authorizes_outline": output["authorizes_outline"]}
            if req["capability"] == "intent.assess" else
            {"summary_points": output["summary_points"]})))
    task = core.attach("demo.agent.task", AsyncRunAdapter(
        AsyncShapedTask(),
        to_input=lambda req, ctx: ctx.resolve(req["context_refs"][0]["ref"]),
        from_response=lambda output, _req: output))
    corr = "demo-interop-001"
    ref1 = core.put_context(conv, ref="ctx:v03/intent", version="v1", scope="session.intent",
        value={"topic": "agent collaboration"}, readers={reason.agent_id}, correlation_id=corr)
    r1 = core.dispatch(conv, core.new_request(conv, contract_id="demo.three-agent.intent.v1",
        correlation_id=corr, context_refs=[ref1], data={"intent": "Make an outline"}))
    ref2 = core.put_context(reason, ref="ctx:v03/instructions", version="v1",
        scope="workspace.instructions", value={"topic": r1["output"]["source_topic"]},
        readers={task.agent_id}, correlation_id=corr)
    decision = core.issue_decision(reason, correlation_id=corr,
        contract_id="demo.three-agent.execute.v1", recipient_id=task.agent_id,
        capability="task.execute", authorized=r1["output"]["authorizes_outline"] is True)
    r2 = core.dispatch(reason, core.new_request(reason,
        contract_id="demo.three-agent.execute.v1", correlation_id=corr,
        context_refs=[ref2], data={"operation": "create_outline"},
        decision_ref=decision, idempotency_key="interop-001"))
    ref3 = core.put_context(task, ref="ctx:v03/receipt", version="v1", scope="task.receipt",
        value=r2["output"], readers={reason.agent_id}, correlation_id=corr)
    r3 = core.dispatch(task, core.new_request(task, contract_id="demo.three-agent.report.v1",
        correlation_id=corr, context_refs=[ref3], data={"receipt_id": "receipt-v03"}))
    ref4 = core.put_context(reason, ref="ctx:v03/summary", version="v1",
        scope="workspace.summary", value={"points": r3["output"]["summary_points"]},
        readers={conv.agent_id}, correlation_id=corr)
    r4 = core.dispatch(reason, core.new_request(reason,
        contract_id="demo.three-agent.response.v1", correlation_id=corr,
        context_refs=[ref4], data={"style": "concise"}))
    assert sum(e["event"] == "completed" for e in core.events) == 4
    assert sum(e["event"] == "context_resolved" for e in core.events) == 4
    print("CAAIF Core SDK v0.3 — Framework adapter smoke demo (test doubles)")
    print("Conversational (callable) → Reasoning (graph API) → Task (async API) → Reasoning → Conversational")
    print(r4["output"]["message"])
    print("Interactions completed: 4")
    print("Authorized context reads: 4")
    return core


if __name__ == "__main__":
    demo()
