> **Internal RC1 notice:** This document originated in an earlier SDK/release-preparation draft. For protected effects, the v0.13 guarded trust specification overrides any older wording about model-issued trusted decisions. Public publication requires the explicit release approvals described in `docs/RC1_RELEASE_STATUS.md`.

# CAAIF Core 0.1.0 Developer Preview — Draft Release Notes

**NOT YET RELEASED.** This draft intentionally precedes legal/security sign-off.

## Highlights

- Core protocol draft and optional Three-Agent Reference Profile (Conversational → Reasoning → Task).
- Reference in-process Controller and independent context-provider experiments.
- Context scoping, versioning, selective retrieval, revocation and reuse prototypes.
- Demonstrations of interoperability using LangGraph and Microsoft Agent Framework interfaces.
- Consolidated validation workflow with automated SDK, profile, example schema and integrated smoke checks.

## Known limitations

- Experimental interfaces and draft protocol subject to incompatible changes.
- No production workload-identity binding, WAN/TLS security guarantee, third-party audit or certified tenant isolation.
- Performance reported on localhost with synthetic data; no equivalent-control A2A benchmark or real-model token-cost study.
- Core does not guarantee exactly-once tool execution or business workflow durability.
- Independent code ownership, third-party license and brand review pending.

## Validation evidence

Use the *actual* latest `validation_reports/latest/report.md` generated from the release commit. Do not hard-code a claimed passing count without reproducing it on the release artifact.
