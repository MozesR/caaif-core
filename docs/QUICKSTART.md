> **Internal RC1 notice:** This document originated in an earlier SDK/release-preparation draft. For protected effects, the v0.13 guarded trust specification overrides any older wording about model-issued trusted decisions. Public publication requires the explicit release approvals described in `docs/RC1_RELEASE_STATUS.md`.

# Five-minute developer quickstart (developer preview candidate)

Requirements: Python >=3.11; optional framework integrations use separate extras.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python examples/sdk_three_agent_demo.py
.venv/bin/python -m unittest discover -s sdk_tests -v
```

The demonstration uses local deterministic Conversational, Reasoning and Task roles, a CAAIF interaction controller and scoped context. This is **not** a production-secure networked agent runtime.

For cross-framework tests, install `.venv/bin/python -m pip install -e '.[interop,schema]'` and execute `.venv/bin/python examples/sdk_cross_framework_v04_demo.py` (must be verified against actual supported framework releases).

CAAIF Core does not mandate three agents. The Three-Agent Reference Profile does enforce the specified role separation when chosen; see `spec/THREE_AGENT_PROFILE.md`.
