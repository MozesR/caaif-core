"""A stand-alone process exposing a generic CAAIF agent handler over loopback.

Usage is managed automatically by sdk_three_agent_http_demo.py.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core.http_transport import AgentHTTPServer

IDS = {"conversational": "demo.agent.conversational",
       "reasoning": "demo.agent.reasoning", "task": "demo.agent.task"}


def agent_handler(role):
    def handle(request, context):
        if role == "conversational" and request["capability"] == "response.compose":
            summary = context.resolve(request["context_refs"][0]["ref"])
            return {"message": "Here is your outline: " + "; ".join(summary["points"])}
        if role == "reasoning" and request["capability"] == "intent.assess":
            intent = context.resolve(request["context_refs"][0]["ref"])
            return {"plan": "Prepare outline", "source_topic": intent["topic"], "authorizes_outline": True}
        if role == "reasoning" and request["capability"] == "task.report":
            receipt = context.resolve(request["context_refs"][0]["ref"])
            return {"summary_points": receipt["points"]}
        if role == "task" and request["capability"] == "task.execute":
            instructions = context.resolve(request["context_refs"][0]["ref"])
            return {"points": ["What it is", "How it works", "Why it matters"],
                    "topic": instructions["topic"]}
        raise ValueError("capability_not_supported")
    return handle


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: http_agent_worker.py ROLE PORT")
    role, port_string = sys.argv[1:]
    if role not in IDS:
        raise SystemExit("unknown role")
    token = os.environ["CAAIF_WORKER_SECRET"]
    worker = AgentHTTPServer(agent_id=IDS[role], auth_token=token,
                             handler=agent_handler(role), port=int(port_string))
    print(f"CAAIF remote {role} agent ready", flush=True)
    try:
        worker.serve_forever()
    finally:
        worker.close()


if __name__ == "__main__":
    main()
