# CAAIF Open-Source Developer Preview — Release Checklist

**Status: NOT APPROVED.** Maintainer and reviewer must mark these items after collecting evidence; do not automatically check them off.

## P0 — required for first public developer preview

- [ ] Identify copyright owner(s); review employment/client IP terms and obtain permission to distribute.
- [ ] Complete provenance inventory, including AI-assisted code and externally sourced examples.
- [ ] Review transitive and bundled third-party licenses; satisfy copyright/NOTICE attribution obligations.
- [ ] Formally approve Apache-2.0; adopt a root `LICENSE`; confirm PyPI metadata and source SPDX tagging.
- [ ] Confirm `caaif-core` name availability, project ownership and branding.
- [ ] Publish SECURITY.md with a verified confidential reporting channel; enable GitHub private vulnerability reporting.
- [ ] Assign named maintainers/security responders and approve governance and contribution policy.
- [ ] Review README for real quickstart, experimental status, tested versions, architecture and no unsupported security claims.
- [ ] Validate fresh installation (wheel and sdist), optional extras, examples, checksums and release metadata.
- [ ] Confirm CI validation and pull-request protections; no leaking secrets in workflows/logs.
- [ ] Record actual named signoffs in `RELEASE_APPROVALS.json`; run `tools/release_gate.py --strict`; capture exact commit hash, tag and written release decision.
- [ ] Strip private keys, test artifacts, project/client data, `.venv`, audit DBs and unpublished credentials.
- [ ] Publish only a clearly labelled **developer preview**, not certified enterprise software or stable v1.0.

## P1 — expected for stable v1.0 / enterprise claims

- [ ] Threat-model review and adversarial tests for spoofing, context leakage, replay and revocation races.
- [ ] TLS/mTLS/workload identity and least-privilege runtime isolation validated on an actual distributed deployment.
- [ ] WAN/TLS and concurrency/load/failure tests.
- [ ] Equivalent-security/governance A2A comparison with reproducible methodology.
- [ ] Real LLM token/cost/context-correctness benchmark on representative non-sensitive tasks.
- [ ] Independent security review and remediation.
- [ ] Public conformance specification and versioned protocol/API compatibility policy.

## Final sign-off (manual, never automatic)

- Rights holder: __________ Date: __________
- Maintainer: __________ Date: __________
- Security reviewer: __________ Date: __________
- Release manager: __________ Date: __________
- Release commit/tag: __________
- Release decision: [ ] APPROVED AS EXPERIMENTAL DEVELOPER PREVIEW  [ ] NOT APPROVED
