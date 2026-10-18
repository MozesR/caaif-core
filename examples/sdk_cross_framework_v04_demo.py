"""CAAIF Core v0.4 — real LangGraph + Microsoft Agent Framework interoperability.

Role mapping:
  Conversational: Python callable
  Reasoning:       compiled LangGraph graph
  Task:            Microsoft Agent Framework functional workflow.as_agent()

The Microsoft component is a REAL framework agent-compatible workflow, not a
model-backed AI agent. It executes deterministic synthetic behavior to allow a
no-credential interoperability demonstration. This does not test LLM quality.

Requirements (optional and not core dependencies):
  python -m pip install 'langgraph>=1,<2' agent-framework-core
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from caaif_core import LocalController
from caaif_core.framework_adapters import CallableAgentAdapter, GraphInvokeAdapter
from caaif_core.microsoft_bridge import microsoft_task_adapter

try:
    from langgraph.graph import StateGraph, START, END
except ImportError as exc:
    raise SystemExit("Install LangGraph: .venv/bin/python -m pip install 'langgraph>=1,<2'") from exc
try:
    from agent_framework import workflow
except ImportError as exc:
    raise SystemExit("Install Microsoft Agent Framework: .venv/bin/python -m pip install agent-framework-core") from exc

PROFILE = ROOT / "examples" / "three-agent"


class ReasoningState(TypedDict, total=False):
    capability: str
    context: dict
    source_topic: str
    authorizes_outline: bool
    summary_points: list[str]


def reason_node(state: ReasoningState) -> dict:
    if state["capability"] == "intent.assess":
        return {"source_topic": state["context"]["topic"], "authorizes_outline": True}
    if state["capability"] == "task.report":
        return {"summary_points": state["context"]["points"]}
    raise ValueError("unknown_reasoning_capability")


@workflow(name="caaif_outline_task", description="Deterministic outline task for interoperability validation")
async def outline_task(topic: str) -> str:
    # A real Microsoft Agent Framework workflow, but no LLM is invoked.
    return json.dumps({"topic": topic, "points": ["What it is", "How it works", "Why it matters"]})


def main() -> None:
    graph_builder = StateGraph(ReasoningState)
    graph_builder.add_node("reason", reason_node)
    graph_builder.add_edge(START, "reason")
    graph_builder.add_edge("reason", END)
    compiled_graph = graph_builder.compile()
    microsoft_agent = outline_task.build().as_agent(name="CAAIFOutlineTask")

    profile = json.loads((PROFILE / "profile.json").read_text())
    contracts = [json.loads(p.read_text()) for p in (PROFILE / "contracts").glob("*.json")]
    core = LocalController(
        profile=profile,
        contracts=contracts,
        policy=lambda req, _contract: req["correlation_id"].startswith("demo-"),
        effect_policy=lambda req, _contract: req["input"].get("operation") == "create_outline",
    )

    conversational = core.attach("demo.agent.conversational", CallableAgentAdapter(
        lambda req, ctx: {"message": "Here is your outline: " + "; ".join(
            ctx.resolve(req["context_refs"][0]["ref"])["points"])}))
    reasoning = core.attach("demo.agent.reasoning", GraphInvokeAdapter(
        compiled_graph,
        to_state=lambda req, ctx: {"capability": req["capability"],
            "context": ctx.resolve(req["context_refs"][0]["ref"])},
        from_state=lambda output, req: (
            {"source_topic": output["source_topic"], "authorizes_outline": output["authorizes_outline"]}
            if req["capability"] == "intent.assess" else
            {"summary_points": output["summary_points"]})))
    task = core.attach("demo.agent.task", microsoft_task_adapter(microsoft_agent))

    corr = "demo-crossframework-001"
    ref1 = core.put_context(conversational, ref="ctx:v04/intent", version="v1",
        scope="session.intent", value={"topic": "agent collaboration"},
        readers={reasoning.agent_id}, correlation_id=corr)
    r1 = core.dispatch(conversational, core.new_request(conversational,
        contract_id="demo.three-agent.intent.v1", correlation_id=corr,
        context_refs=[ref1], data={"intent": "Make an outline"}))

    ref2 = core.put_context(reasoning, ref="ctx:v04/instructions", version="v1",
        scope="workspace.instructions", value={"topic": r1["output"]["source_topic"]},
        readers={task.agent_id}, correlation_id=corr)
    decision = core.issue_decision(reasoning, correlation_id=corr,
        contract_id="demo.three-agent.execute.v1", recipient_id=task.agent_id,
        capability="task.execute", authorized=r1["output"]["authorizes_outline"] is True)
    r2 = core.dispatch(reasoning, core.new_request(reasoning,
        contract_id="demo.three-agent.execute.v1", correlation_id=corr,
        context_refs=[ref2], data={"operation": "create_outline"},
        decision_ref=decision, idempotency_key="crossframework-001"))

    ref3 = core.put_context(task, ref="ctx:v04/receipt", version="v1", scope="task.receipt",
        value=r2["output"], readers={reasoning.agent_id}, correlation_id=corr)
    r3 = core.dispatch(task, core.new_request(task,
        contract_id="demo.three-agent.report.v1", correlation_id=corr,
        context_refs=[ref3], data={"receipt_id": "receipt-v04"}))

    ref4 = core.put_context(reasoning, ref="ctx:v04/summary", version="v1",
        scope="workspace.summary", value={"points": r3["output"]["summary_points"]},
        readers={conversational.agent_id}, correlation_id=corr)
    r4 = core.dispatch(reasoning, core.new_request(reasoning,
        contract_id="demo.three-agent.response.v1", correlation_id=corr,
        context_refs=[ref4], data={"style": "concise"}))
    completed = sum(e["event"] == "completed" for e in core.events)
    resolved = sum(e["event"] == "context_resolved" for e in core.events)
    assert (completed, resolved) == (4, 4)
    print("CAAIF Core SDK v0.4 — Real cross-framework smoke test")
    print("Conversational (Python) → Reasoning (LangGraph) → Task (Microsoft Agent Framework)")
    print(r4["output"]["message"])
    print(f"Interactions completed: {completed}")
    print(f"Authorized context reads: {resolved}")
    print("Task runtime: real Microsoft Agent Framework workflow.as_agent()")
    print("No LLM used; deterministic framework interop validation")


if __name__ == "__main__":
    main()
