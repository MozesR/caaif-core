# CAAIF Core — Open-Source Release Preparation Package

**Target:** first public *developer preview* (suggested package version `0.1.0.dev0`), **not** a production-approved or stable CAAIF v1.0 standard.

This is a non-destructive overlay for the **CAAIF Core SDK project** (not the old Sales/Finance PoC). It includes release governance documents, a Python distribution configuration, GitHub CI, and a release gate. It does **not** modify `caaif_core/`, replace your `README.md`, publish to GitHub/PyPI, or grant a license on the author's behalf.

## Quick application to your open VS Code project

1. Preserve a backup or Git commit of the current project.
2. Extract ZIP from the project root with `unzip -n ~/Downloads/CAAIF_Open_Source_Release_Preparation_Package.zip -d .`.
3. Review `docs/RELEASE_DECISIONS.md` and `docs/LEGAL_AND_PROVENANCE.md` (copyright owner, work-for-hire/IP assignments, external material, dependencies, trademark and repository choice).
4. Locally install in editable mode, **for evaluation only**: `.venv/bin/python -m pip install -e .` (a virtual environment with setuptools is required).
5. Run `.venv/bin/python tools/release_gate.py` and `.venv/bin/python -m unittest discover -s release_tests -v`.
6. Once rights are cleared, a rights holder can choose to **formally adopt** Apache 2.0 using `docs/LICENSE_ADOPTION.md`. Until then leave the legal draft as `LICENSE.Apache-2.0.PROPOSED`.
7. After actual review, record signoffs in `RELEASE_APPROVALS.json` using `docs/RELEASE_APPROVALS.example.json`; the gate checks declarations but not their legal truth. Set up private vulnerability reporting before a public GitHub repository is enabled; see `SECURITY.md`.

The current `pyproject.toml` deliberately **does not claim a license and excludes proposed legal drafts from wheel license metadata**: this is an internal packaging candidate. Without a rights-holder-approved `LICENSE` file and metadata, it must not be uploaded to PyPI or published as open source. Naming `caaif-core` is also provisional; validate availability and conflicts before publishing.

## Package contents

| Item | Location |
|---|---|
| Full Apache 2.0 license text, NOT yet adopted | `LICENSE.Apache-2.0.PROPOSED` |
| License selection and copyright/provenance review | `docs/LICENSE_ADOPTION.md`, `docs/LEGAL_AND_PROVENANCE.md` |
| Attribution inventory template | `NOTICE.PROPOSED.md`, `docs/PROVENANCE_INVENTORY.csv` |
| Security reporting & trust boundaries | `SECURITY.md`, `docs/THREAT_MODEL.md` |
| Contributions & community expectations | `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md` |
| Flat-layout Python packaging | `pyproject.toml`, `MANIFEST.in` |
| Packaging/release procedure | `docs/PACKAGING.md`, `docs/RELEASE_PROCESS.md`, `docs/RELEASE_NOTES_0.1.0.md` |
| User-facing project README candidate | `README_PUBLIC_CANDIDATE.md` |
| Automation & templates | `.github/workflows/caaif-release-checks.yml`, `.github/dependabot.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/` |
| Review gate, never approves security | `tools/release_gate.py`, `release_tests/` |
| Review checklist | `RELEASE_CHECKLIST.md` |

## Explicit limitations and gates

The v0.10/v0.11 integrated demonstrations are localhost research tests. There is no claimed production-grade network identity, independent security audit, comparable A2A benchmark, WAN testing, or real LLM token/cost benchmark. Passing tests is **not** legal or security approval.

**Relevant authoritative references**: https://www.apache.org/licenses/LICENSE-2.0 ; https://apache.org/legal/apply-license.html ; https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ ; https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy .
