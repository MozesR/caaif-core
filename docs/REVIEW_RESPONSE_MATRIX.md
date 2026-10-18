# Review response matrix - 18 October 2026

| Reviewer issue | v0.12 action | Status |
|---|---|---|
| Reasoning decision treated as trusted | New untrusted proposal, host registered intent, independent policy and action-bound permit | Implemented locally; distributed threat model open |
| Context taint/provenance | Trusted local provenance labels, conservative label merge, host-mediated disclosure check | Partial; arbitrary LLM transformation not fully tracked |
| Comparison to CaMeL and dual-LLM | Added conceptual comparison and boundaries; no claim of unique prompt-injection solution | Documented |
| Falsifiability | Four RQ hypotheses with measurable proposed acceptance criteria and disclosures | Specified; adversarial study pending |
| Related work thin | CaMeL, design patterns, dual LLM, Cedar/XACML, SPIFFE, A2A, OAuth Token Exchange | Expanded |
| Bytes overemphasized | Primary metrics: unnecessary disclosure and forbidden-action bypass; traffic and latency secondary | Reframed |
| Benchmark reporting | Explicit run/sample figures, omitted networking/model cost, reproducibility gaps | Documented; new matched-control benchmark pending |
| Three-Agent sequence diagram inconsistent | New figure shows 4 gated role edges and task tool-gateway check | Updated |
| Permit/replay/signature/revocation semantics | Local opaque permit with exact binding, TTL, nonce and single-use gateway; production issuer/sender and revocation requirements stated | Local prototype; network implementation pending |
| Author/affiliation and public artifact links | Labeled as pending; no invented authors, repository tag or DOI | Pending |
| Inconsistent expansion | Canonical expansion: Context-Aware Agent Interaction Framework | Standardized |

## Material residual risks

- The old `LocalController.issue_decision(... authorized=True)` remains in the *legacy research mode*. It is disabled only in `GuardedLocalController`. A publication must not present legacy protected-effects as safe.
- A malicious Task handler running in the same Python process can bypass any Python wrapper if it has other network, filesystem or API credentials.
- Provenance metadata is assigned by trusted host calls, but full lineage through arbitrary LLM synthesis is not tracked.
- The local permit is an opaque in-memory reference, not a signed or sender-constrained token.
- The guarded profile is not yet connected to the independent HTTP Context Provider and real LangGraph / Microsoft Agent Framework under adversarial model behavior.
- No external penetration test, tenant crossing, external A2A equivalent controls study, or model-token cost benchmark has been completed.

**Release recommendation:** treat this as an experimental trust-profile design. Block v1.0 security claims until residual P0/P1 deployment controls and independent tests are complete.
