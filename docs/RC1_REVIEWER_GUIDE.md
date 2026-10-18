# Reviewer guide

Prefer beginning with `spec/TRUST_ARCHITECTURE_DRAFT3.md`, `spec/GUARDED_DISTRIBUTED_PROFILE_V013.md` and `docs/RC1_SECURITY_ASSESSMENT.md`.

## Reproduce without secrets
1. Install SDK editable into a fresh virtual environment (`INSTALL_RC1.md`).
2. Run all SDK tests and the three-agent profile suite.
3. Run the guarded local and guarded distributed demonstrations.
4. Run schema tests with jsonschema; run cross-framework smoke with optional interop dependencies.
5. Run `tools/validate_release.py --mode full --out validation_reports/latest` if installed packages and platform support it.
6. Run `tools/release_gate.py --strict` — it must BLOCK until human approvals and actual LICENSE adoption.

## Adversarial coverage still needed
A threat actor with direct OS/tool credentials bypassing the gateway; forged application intent; stale and cross-tenant context access; unknown policy version; replay across multiple gateway nodes; permit revocation racing with execution; ambiguous remote actions; untrusted derived-output lineage; authentic LLM prompt injection. No existing passing synthetic test substitutes for an independent audit.
