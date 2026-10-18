> **Internal RC1 notice:** This document originated in an earlier SDK/release-preparation draft. For protected effects, the v0.13 guarded trust specification overrides any older wording about model-issued trusted decisions. Public publication requires the explicit release approvals described in `docs/RC1_RELEASE_STATUS.md`.

# Maintainer release procedure — developer preview

1. Freeze scope and version; ensure a clean, reviewed Git commit.
2. Finalize `docs/RELEASE_DECISIONS.md`, ownership inventory, approved Apache 2.0 `LICENSE`/NOTICE, optional CLA/DCO policy and security-reporting route.
3. Audit package source, dependencies, examples, provenance, untracked files and commit history for sensitive information.
4. Verify Python packaging metadata, repository URL, README and license consistency; check package name availability.
5. Create an approved `RELEASE_APPROVALS.json` based on `docs/RELEASE_APPROVALS.example.json` with actual signatories, date and commit (no secrets); this is an auditable assertion, **not** independently verified by the script. Run: `python -m unittest discover -s sdk_tests -v`, `python tools/validate_release.py --mode full`, `python tools/release_gate.py --strict`.
6. Build sdist and wheel with `.venv/bin/python -m build`; inspect archives; run `.venv/bin/python -m twine check dist/*`; install wheel into an empty venv and execute quickstart.
7. Run mandatory CI on the exact release commit. Pin and audit third-party actions; include SBOM/dependency audit and security sign-offs.
8. Choose a pre-release tag such as `v0.1.0-dev.0`, publish GitHub release with clear **experimental/developer preview** label and checksum, after formal approval; PyPI upload is an independent decision.
9. Monitor issues and private security advisories; capture community feedback and file compatibility improvements before considering stable 1.0.

The release gate produces technical evidence only; it does not approve legal rights or production security.
