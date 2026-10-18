"""CAAIF SDK v0.2: interchangeable agent-handler invocation interfaces.

AgentHandlerTransport is deliberately agnostic about framework, model, or API.
Authorization is performed by LocalController, not by a transport.
"""
from __future__ import annotations
from typing import Any, Callable, Protocol


class AgentHandlerTransport(Protocol):
    def __call__(self, request: dict[str, Any], context: Any) -> dict[str, Any]:
        """Invoke one registered recipient handler with authorized context access."""
        ...


class InProcessTransport:
    """Adapter for an existing (request, context) -> dict agent handler."""

    def __init__(self, handler: Callable[[dict, Any], dict]):
        if not callable(handler):
            raise TypeError("handler_must_be_callable")
        self._handler = handler

    def __call__(self, request: dict, context: Any) -> dict:
        return self._handler(request, context)
