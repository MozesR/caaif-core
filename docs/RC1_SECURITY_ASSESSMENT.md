# RC1 Security Assessment and Explicit Scope

Status: **internal security-review candidate only**. This document is a gap assessment, not an external security audit.

## Controls demonstrated in synthetic localhost tests

- Trusted host intent is distinct from model-authored proposals; attempts to treat untrusted source instructions as authority are rejected by the guarded path.
- Independent policy compares the exact action, resource, parameter digest, context references, contract and purpose.
- A separate Tool Gateway verifies short-lived action-bound authorization, the authenticated task role and replay registry before running registered tools.
- Context Provider checks scopes, versions, field-level grants and revocation at retrieval.
- Guarded egress checks declared provenance/lineage when applications use the authorized gateway.
- A multi-process deterministic demo exercises six localhost processes and negative scenarios.

## Unresolved (block production security assertions)

| Gate | Why it matters | Evidence required |
|---|---|---|
| Workload identities and isolation | Static localhost bearer keys are not independently managed workload identities | mTLS or SPIFFE-backed deployment with secret and principal isolation |
| Tool gateway bypass | A process with direct network/system tool credentials can bypass the guard | Network egress and downstream entitlements denying direct access |
| Durable replay protection | In-memory nonce ledger can be reset after a crash | Durable atomic idempotency at destination, multi-node tests |
| Contract policy and provenance trust | Registry and labels assume trusted host/ingestion | Signed/approved contracts, trusted metadata pipeline, audit |
| Revocation races | Check-then-execute allows TOCTOU unless action boundary locks/versions inputs | Defined revocation SLA and concurrent mutation tests |
| Full four-edge enforcement | Protected Reasoning→Task guarded; all four distributed edges not yet fully composed under profile G | Conformance tests for each role edge and return path |
| Output disclosure and derived context | Host-supplied lineage can be incomplete | End-to-end trusted lineage or fail-closed complete egress mediation |
| Network and adversarial security | No TLS/WAN/hostile-process testing; no actual LLM prompt injection suite | Independent penetration/LLM security evaluation |
| Distributed A2A interoperability | Mappings remain proposals | Conformance against real A2A and equivalent-control benchmark |

In-process Profile L protects the **modeled agent behavior**, not malicious Python inside the same process. Distributed v0.13 is a **localhost reference** only.

## Review workflow

The reviewer should reproduce the regression suite, audit `caaif_core/guarded.py` and `distributed_guard_v013.py`, validate the Context Provider policy path and verify all bypass and revocation cases. Record findings in a tracked private security review before changing any distribution status.
