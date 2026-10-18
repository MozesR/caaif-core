# CAAIF Core v0.1.0rc1 — Release Candidate Validation Report

**Date:** 18 October 2026  
**State:** INTERNAL CANDIDATE — **NOT APPROVED FOR PUBLICATION**

## Validation evidence

| Validation | Result | Notes |
|---|---|---|
| SDK regressions | **PASS — 161/161** | 12 module-level subprocess runs, each with a bounded timeout; see `docs/RC1_SDK_TEST_SUMMARY.json` |
| Three-Agent profile fixture tests | **PASS — 15/15** | Existing reference profile fixtures |
| Release-preparation / package identity tests | **PASS — 9/9** | Missing active license is checked deliberately |
| Schema fixtures | **PASS — 14 objects** | Existing JSON schema example validator |
| Guarded local demo | **PASS** | Independently authorized action and hostile-instruction rejection (deterministic scenario) |
| Guarded distributed demo | **PASS** | Six localhost processes, authorization, context revocation, duplicate protection (research only) |
| Integrated wire tests | **PASS — 2/2** | Local HTTP traffic and revocation |
| Operation profiler tests | **PASS — 2/2** | Four operation categories |
| Integrated operation benchmark | **PASS (functional)** | Five-run synthetic smoke; no baseline superiority claim |
| Package wheel | **PASS** | Built with setuptools and clean-imported after local installation; no active license metadata |
| Package source archive | **PASS** | Built locally; no signing or release publication |
| Strict release gate | **BLOCKED (expected)** | Missing formal license adoption and release approvals |

The legacy single-process `unittest discover -s sdk_tests -v` intermittently stalled in the execution environment during remote-service fixture cleanup. To avoid misreporting that as a pass, the 12 SDK modules were individually run in bounded subprocesses and their outcomes consolidated. The existing development machine had previously completed the combined 161-test suite. This is an engineering/test-stability item for CI monitoring, not proof that every platform is reliable.

## Validated local code behavior, not production security

- In-process guarded profile verifies trusted-host intent against an untrusted Reasoning proposal and enforces action-bound registered-tool execution.
- Six-process localhost guarded demo verifies separate local process actors, a Context Provider and a Tool Gateway, but uses static bearer secrets/shared proof tokens and an in-memory replay ledger.
- The distributed guarded profile does **not** establish production TLS, strong workload identity, tenant isolation, bypass-resistant network policy, complete provenance tracking, or all four role-edge checks under a single deployment-grade boundary.
- No independent security audit, real LLM injection benchmark, WAN concurrency test, A2A equivalent-control benchmark, or token/cost comparison was completed in this candidate.

## Release decision

**Hold public publication.** The project ships a staged `LICENSE.Apache-2.0.PROPOSED`, **not an adopted license**. Ownership/provenance, maintainer attribution, private vulnerability reporting, dependency review, security review, and formal release approvals must be completed by appropriate rights holders. This candidate is for local review; it is not an official open-source or production release.

Review `docs/RC1_RELEASE_STATUS.md`, `docs/RC1_SOURCE_AND_LICENSE.md`, `SECURITY.md`, and `RELEASE_CHECKLIST.md` before proposing a public Developer Preview.
