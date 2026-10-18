# CAAIF Core v0.1.0rc1 — developer preview candidate

**Local evaluation only. Do not publish to GitHub/PyPI before signed licensing, provenance and security release decisions.**

This is a **new, consolidated project**; do not extract on top of your original CAAIF development project. Keep that project as a backup/research history.

## macOS / Linux

```bash
cd CAAIF_Core_0.1.0rc1_Developer_Preview
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python examples/sdk_guarded_three_agent_demo.py
.venv/bin/python examples/sdk_guarded_distributed_v013_demo.py
.venv/bin/python tools/run_sdk_tests.py --timeout 75
.venv/bin/python -m unittest discover -s tests -p 'test_three_agent_profile.py' -v
```

Optional dependencies for schema and cross-framework checks:

```bash
.venv/bin/python -m pip install -e '.[dev,interop]'
.venv/bin/python tests/validate_examples.py
.venv/bin/python examples/sdk_cross_framework_v04_demo.py
```

## Build and verify a wheel without publishing

```bash
.venv/bin/python -m pip install build twine
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
.venv/bin/python tools/release_gate.py --strict
```

The **last command should fail** while license/approval blockers remain. This is intentional, not a test failure.

The Python distribution version (`0.1.0rc1`) is distinct from the earlier *draft v1.0 protocol specification* and *v0.13 research module labels*. The protocol is not a ratified v1.0 standard.
