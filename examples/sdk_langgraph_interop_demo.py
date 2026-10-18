"""Real LangGraph reasoning component in a CAAIF three-role collaboration.

Optional dependency: python3 -m pip install 'langgraph>=1,<2'
No LLM, provider credential, database, or remote service is required.
This demonstrates LangGraph integration, not an LLM reasoning-quality benchmark.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.sdk_framework_adapter_demo import demo

try:
    from langgraph.graph import StateGraph, START, END
except ImportError as exc:
    raise SystemExit("Install the optional dependency: python3 -m pip install 'langgraph>=1,<2'") from exc


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


def main():
    graph = StateGraph(ReasoningState)
    graph.add_node("reason", reason_node)
    graph.add_edge(START, "reason")
    graph.add_edge("reason", END)
    compiled = graph.compile()
    demo(reasoning_graph=compiled)
    print("Reasoning runtime: actual compiled LangGraph graph")


if __name__ == "__main__":
    main()
