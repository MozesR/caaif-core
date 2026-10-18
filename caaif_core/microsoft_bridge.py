"""Optional bridge between CAAIF Core and Microsoft Agent Framework agent.run.

No dependency on agent_framework; callers inject an actual Agent / workflow.as_agent().
This module only maps approved CAAIF context to an agent's input, then validates
its result. All authorization remains with LocalController.
"""
from __future__ import annotations

import json
from typing import Any

from .framework_adapters import AsyncRunAdapter


def _task_prompt(request: dict, context: Any) -> str:
    refs = request.get("context_refs")
    if not isinstance(refs, list) or len(refs) != 1 or not isinstance(refs[0], dict):
        raise ValueError("exactly_one_context_reference_required")
    approved = context.resolve(refs[0]["ref"])
    if not isinstance(approved, dict) or not isinstance(approved.get("topic"), str):
        raise ValueError("invalid_task_context")
    topic = approved["topic"].strip()
    if not topic:
        raise ValueError("empty_task_topic")
    # Only release the permitted topic, never user history, hidden policy, etc.
    return topic


def _task_result(response: Any, _: dict) -> dict:
    raw = getattr(response, "text", None)
    if not isinstance(raw, str):
        raise ValueError("agent_response_text_required")
    try:
        output = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("agent_output_invalid_json") from exc
    if not isinstance(output, dict) or set(output) != {"topic", "points"}:
        raise ValueError("unexpected_agent_output_shape")
    if (not isinstance(output["topic"], str) or not output["topic"].strip()
            or not isinstance(output["points"], list)
            or not output["points"]
            or not all(isinstance(p, str) and p.strip() for p in output["points"])):
        raise ValueError("invalid_agent_output_values")
    return {"topic": output["topic"], "points": output["points"]}


def microsoft_task_adapter(agent: Any) -> AsyncRunAdapter:
    """Wrap any async Microsoft Agent Framework-compatible .run() agent.

    This does not verify the agent runtime. Tests run against stub .run() agents;
    the optional example exercises the actual Microsoft framework package.
    """
    return AsyncRunAdapter(agent, to_input=_task_prompt, from_response=_task_result)
