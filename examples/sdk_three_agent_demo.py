"""Three-role, in-process CAAIF example. No LLM/provider/database required."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core import LocalController
PROFILE = ROOT / "examples" / "three-agent"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def demo():
    profile = read(PROFILE / "profile.json")
    contracts = [read(p) for p in sorted((PROFILE / "contracts").glob("*.json"))]

    # Deliberately simple, independent local admission policies.
    boundary = LocalController(profile=profile, contracts=contracts,
                               policy=lambda req, c: req["correlation_id"].startswith("demo-"),
                               effect_policy=lambda req, c: req["input"].get("operation") == "create_outline")

    def conversation_handler(request, context):
        summary = context.resolve(request["context_refs"][0]["ref"])
        return {"message": "Here is your outline: " + "; ".join(summary["points"])}

    def reasoning_handler(request, context):
        if request["capability"] == "intent.assess":
            intent = context.resolve(request["context_refs"][0]["ref"])
            return {"plan": "Prepare outline", "source_topic": intent["topic"]}
        if request["capability"] == "task.report":
            receipt = context.resolve(request["context_refs"][0]["ref"])
            return {"summary_points": receipt["points"]}
        raise ValueError("unknown_reasoning_capability")

    def task_handler(request, context):
        instructions = context.resolve(request["context_refs"][0]["ref"])
        return {"points": ["What it is", "How it works", "Why it matters"],
                "topic": instructions["topic"]}

    conversational = boundary.attach("demo.agent.conversational", conversation_handler)
    reasoning = boundary.attach("demo.agent.reasoning", reasoning_handler)
    task = boundary.attach("demo.agent.task", task_handler)
    correlation = "demo-outline-001"

    intent_ref = boundary.put_context(conversational, ref="ctx:demo/session/1", version="v1",
                                      scope="session.intent", value={"topic": "agent collaboration"},
                                      readers={reasoning.agent_id}, correlation_id=correlation)
    r1 = boundary.dispatch(conversational, boundary.new_request(
        conversational, contract_id="demo.three-agent.intent.v1", correlation_id=correlation,
        context_refs=[intent_ref], data={"intent": "Make an outline"}))

    instructions = boundary.put_context(reasoning, ref="ctx:demo/instructions/3", version="v1",
                                        scope="workspace.instructions", value={"topic": r1["output"]["source_topic"]},
                                        readers={task.agent_id}, correlation_id=correlation)
    decision_ref = boundary.issue_decision(reasoning, correlation_id=correlation,
                                           contract_id="demo.three-agent.execute.v1",
                                           recipient_id=task.agent_id, capability="task.execute", authorized=True)
    r2 = boundary.dispatch(reasoning, boundary.new_request(
        reasoning, contract_id="demo.three-agent.execute.v1", correlation_id=correlation,
        context_refs=[instructions], decision_ref=decision_ref,
        idempotency_key="outline-001", data={"operation": "create_outline"}))

    receipt = boundary.put_context(task, ref="ctx:demo/task/44", version="v1", scope="task.receipt",
                                   value=r2["output"], readers={reasoning.agent_id}, correlation_id=correlation)
    r3 = boundary.dispatch(task, boundary.new_request(
        task, contract_id="demo.three-agent.report.v1", correlation_id=correlation,
        context_refs=[receipt], data={"receipt_id": "receipt-001"}))

    summary = boundary.put_context(reasoning, ref="ctx:demo/summary/1", version="v1",
                                   scope="workspace.summary", value={"points": r3["output"]["summary_points"]},
                                   readers={conversational.agent_id}, correlation_id=correlation)
    r4 = boundary.dispatch(reasoning, boundary.new_request(
        reasoning, contract_id="demo.three-agent.response.v1", correlation_id=correlation,
        context_refs=[summary], data={"style": "concise"}))

    print("CAAIF Core SDK v0.1 — Three-Agent Demo")
    print("Conversational → Reasoning → Task → Reasoning → Conversational")
    print(r4["output"]["message"])
    print("Interactions completed:", sum(e["event"] == "completed" for e in boundary.events))
    print("Authorized context reads:", sum(e["event"] == "context_resolved" for e in boundary.events))
    return boundary


if __name__ == "__main__":
    demo()
