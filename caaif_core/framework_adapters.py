"""CAAIF SDK v0.3 — small opt-in bridges to independently developed agents.

Adapters translate approved CAAIF requests to a framework's native interface.
They do NOT authorize callers, expand context access, or issue task permits:
those remain responsibilities of LocalController.

No third-party framework is imported here. A LangGraph compiled graph can be
passed through GraphInvokeAdapter; an async Microsoft Agent Framework agent can
be passed through AsyncRunAdapter with explicit input/output mapping.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any


def _object(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f"{label}_must_be_object")
    # Require a portable JSON output, including forbidding NaN and custom types.
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}_not_json_compatible") from exc
    return value


class CallableAgentAdapter:
    """Integrate any synchronous callable(request, context) -> JSON object."""

    def __init__(self, handler: Callable[[dict, Any], dict]):
        if not callable(handler):
            raise TypeError("handler_must_be_callable")
        self._handler = handler

    def __call__(self, request: dict, context: Any) -> dict:
        return _object(self._handler(request, context), "agent_output")


class GraphInvokeAdapter:
    """Integrate graph-style runtimes exposing .invoke(state), e.g. LangGraph.

    Both mappings are explicit. The graph receives only state supplied by
    to_state, which may resolve authorized context references through CAAIF.
    No graph-level tool permission is implied by a CAAIF interaction contract.
    """

    def __init__(self, graph: Any, *, to_state: Callable[[dict, Any], dict],
                 from_state: Callable[[dict, dict], dict]):
        if not callable(getattr(graph, "invoke", None)):
            raise TypeError("graph_invoke_required")
        if not callable(to_state) or not callable(from_state):
            raise TypeError("explicit_graph_mappings_required")
        self._graph = graph
        self._to_state = to_state
        self._from_state = from_state

    def __call__(self, request: dict, context: Any) -> dict:
        state = _object(self._to_state(request, context), "graph_input")
        final = self._graph.invoke(state)
        result = self._from_state(final, request)
        return _object(result, "agent_output")


class AsyncRunAdapter:
    """Integrate asynchronous agent.run(input), e.g. Microsoft Agent Framework.

    Intended for a synchronous CAAIF worker thread or CLI. An existing async
    event loop is not supported; run this adapter in a separate worker thread
    instead. Does not expose model tools or grant the agent external privileges.
    """

    def __init__(self, agent: Any, *, to_input: Callable[[dict, Any], Any],
                 from_response: Callable[[Any, dict], dict]):
        if not callable(getattr(agent, "run", None)):
            raise TypeError("agent_run_required")
        if not callable(to_input) or not callable(from_response):
            raise TypeError("explicit_async_mappings_required")
        self._agent = agent
        self._to_input = to_input
        self._from_response = from_response

    async def _invoke(self, value: Any) -> Any:
        response = self._agent.run(value)
        if not hasattr(response, "__await__"):
            raise TypeError("agent_run_must_be_async")
        return await response

    def __call__(self, request: dict, context: Any) -> dict:
        # Detect an active event loop before creating a coroutine.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("async_adapter_requires_worker_thread")
        value = self._to_input(request, context)
        response = asyncio.run(self._invoke(value))
        return _object(self._from_response(response, request), "agent_output")
