> **Internal RC1 notice:** This document originated in an earlier SDK/release-preparation draft. For protected effects, the v0.13 guarded trust specification overrides any older wording about model-issued trusted decisions. Public publication requires the explicit release approvals described in `docs/RC1_RELEASE_STATUS.md`.

# Python packaging and clean installation

The candidate build explicitly sets `[tool.setuptools] license-files = []` so the unapproved Apache 2.0 proposal is not misrepresented as an adopted license in wheel metadata. After legal approval, configure the accepted LICENSE file for distribution.

The existing project uses a **flat layout**: `caaif_core/` at repository root. The proposed `pyproject.toml` uses explicit `caaif_core*` package discovery rather than accidentally packaging examples/tests as importable distributions. No mandatory framework/LLM/database runtime dependencies are introduced.

## Local build without publishing

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s sdk_tests -v
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

A clean wheel smoke test should use a **fresh** venv, install `dist/*.whl`, then run `python -c 'from caaif_core import LocalController; print(LocalController)'`. Validate sdist/wheel file lists; no credentials, customer datasets, benchmark logs or caches may ship.

## Release blockers

1. The current manifest intentionally has no license claim. Do not upload to PyPI or publish the source as Apache-licensed until the owner selects and approves a license.
2. Check whether the distribution name `caaif-core` is available and not confusingly similar to another project; no reservation is implied.
3. Reconcile `requires-python` with actual tested versions and optional framework support.
4. Freeze a dependency lock/constraints document for reproducible CI where appropriate; produce license inventory and SBOM; scan for secrets.
5. Build and install test from source archive and wheel on a clean environment; validate metadata, README, import behavior, and extras.
6. The initial SDK is experimental; avoid stable `1.0` package version while protocol draft is not final.

See https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ .
