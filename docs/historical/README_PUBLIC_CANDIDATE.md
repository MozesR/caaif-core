# CAAIF Core — Context-Aware Agent Interaction Framework

> **Experimental developer preview. Not production-ready.** Do not use with sensitive data or production tooling without independent security controls and review.

CAAIF is a small, framework-independent SDK for **controlled agent-to-agent interactions** and authorized exchange of **only the context needed**. It can be used with two or more agents. Its optional Three-Agent Reference Profile enforces Conversational / Reasoning / Task separation with a trusted decision before protected Task execution.

CAAIF complements rather than replaces agent frameworks or their task protocols. A2A/MCP interop mappings are proposals, not standards endorsed by their maintainers.

## Local quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python examples/sdk_three_agent_demo.py
.venv/bin/python -m unittest discover -s sdk_tests -v
```

## Architecture

- Interaction Controller: independently checks the interaction contract and policy.
- Context services: selective retrieval, versioned scopes, retrieval-time authorization and revocation.
- Agent adapters: local Python agents, HTTP examples and optional LangGraph/Microsoft Agent Framework adapters.
- Optional modules: context caching/deltas, persistence/reconciliation prototypes (not required by Core).

## Current evidence and limits

Reproducible automated suites and integrated localhost benchmarks are available. Benchmarks do not establish advantages over a comparable A2A deployment, real WAN/TLS behavior, production security, or real-model token consumption. See `SECURITY.md`, `spec/` and `docs/RELEASE_NOTES_0.1.0.md`.

## Status, license and contributors

This candidate README becomes suitable for public use **only once a rights holder formally adopts a license**. See `docs/LICENSE_ADOPTION.md`, `CONTRIBUTING.md` and `GOVERNANCE.md`.
