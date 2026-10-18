> **Status: historical architecture draft.** For effectful work, the guarded trust boundary in `spec/TRUST_ARCHITECTURE_DRAFT3.md` and `spec/GUARDED_DISTRIBUTED_PROFILE_V013.md` supersedes any assumption that an LLM-produced decision is an authorization. This is a developer preview, not a stable security standard.

# CAAIF Core — Conformance and Evaluation Plan

## Conformance ladder

**Schema-only** means JSON examples validate; it is not CAAIF compliance. **Local Profile (L)** requires executable behavior tests for contract authorization, scoped context, consistent terminal outcomes, and redacted observability. **Guarded Profile (G)** additionally requires authenticated service-to-service identities, enforceable dispatch and context boundaries, revocation/expiry at use time, and a bypass/impersonation threat assessment.

## Three-Agent Reference Profile conformance

The profile introduces P01–P08 requirements detailed in [`THREE_AGENT_PROFILE.md`](THREE_AGENT_PROFILE.md). Static fixture checks are in `tests/test_three_agent_profile.py`; they do **not** certify the deployed runtime. A profile-conformant Local or Guarded runtime additionally MUST pass live tests for:

| Test | Expected behavior |
| --- | --- |
| P-C01 | Conversational → Reasoning allowed with correct contract and principal |
| P-C02 | Reasoning → Task allowed only with trusted, unexpired, correlation/recipient/capability-bound reasoning decision |
| P-C03 | Conversational → Task attempt denied; no task or tool execution |
| P-C04 | Caller role spoofing or same principal assigned to Reasoning and Task rejected |
| P-C05 | Task → Reasoning report and Reasoning → Conversational response both separately authorized and audited |
| P-C06 | Task cannot treat reasoning decision as tool permission; independent tool authorization denied where applicable |
| P-C07 | Wrong or stale context version, unapproved scope, revoked contract/decision denied at time of use |
| P-C08 | Effectful task replay with changed input rejected; unknown outcome not automatically retried |

A runtime with arbitrary two-agent wiring can claim **Core conformance**, not **Three-Agent Profile conformance**. For either claim, cross-framework interoperability and security need separate verification.

## Minimum independent test cases

| ID | Scenario | Required expected outcome |
| --- | --- | --- |
| C01 | Matching principal, valid contract, scope and TTL | Interaction allowed and correctly correlated |
| C02 | Unknown contract/capability | Deny and audit reason |
| C03 | Claimed caller differs from authenticated principal | Deny; no dispatch |
| C04 | Wrong recipient, contract version or capability | Deny; no dispatch |
| C05 | Extra context scope | Deny or return only explicitly authorized projection |
| C06 | Context ref version changed between authorization and retrieval | Reject stale version; no silent substitution |
| C07 | Revoked or expired permit at dispatch | Deny |
| C08 | Duplicate `request_id` with changed content | Conflict, not new execution |
| C09 | Effectful action acknowledgement lost | Reconcile/hold; no automatic duplicate effect |
| C10 | Policy engine unavailable | Fail closed |
| C11 | No history/context in proposal | Allowed when contract permits empty context |
| C12 | Large context below/above inline threshold | Adaptive path selects measured cheaper valid strategy |
| C13 | Event/audit sanitization | No tokens, raw customer data, or private reasoning |
| C14 | Bypass dispatch through non-CAAIF interface (Guarded) | Blocked by recipient or gateway |
| C15 | Concurrency and tenant separation (Guarded) | Distinct principals cannot cross-read or cross-approve |
| C16 | Optional A2A adapter with independent agent stack | Interoperable task and metadata mapping |

## Benchmark design

Test four experimental arms:

- Bare direct HTTP — latency and bytes floor; explicitly not governance-equivalent.
- Governed non-CAAIF baseline — same identity, policy, scope and audit enforcement.
- CAAIF local/guarded — same workload and models.
- A2A (with and without CAAIF extension, if feasible) — protocol interoperability assessment.

For each measure `p50/p95/p99`, internal and external HTTP body + header bytes, message count, number of context versions retrieved, redundant bytes, model input/output tokens, decision correctness, unauthorized-dispatch rate, context leakage rate, retries, recovery outcomes, setup steps, dependencies and configuration burden. Use scenarios with 0.2 KB, 2 KB, 20 KB, 200 KB contexts and 1/2/5/10 context reuses, as illustrative test levels rather than predetermined wins. Run randomized repeated tests on documented environments. Include cold/warm and network-separated runs. Never report savings relative to bare HTTP as proof of a better governed protocol.

## Release gates

1. At least one executable Python reference adapter with no banking-specific dependencies.
2. A three-role reference demonstration, a core-only two-agent compatibility sample, and an A2A adapter (at least two independently implemented agent integrations).
3. Public conformance suite passing C01-C16 as applicable to declared profile.
4. Security design review, including permit forgery, context provider SSRF, tenant isolation and prompt injection.
5. Benchmarks demonstrating meaningful improvements for at least one context regime with no loss of safety or quality.
6. Repository governance, contributor guidelines, license/ownership review, versioning and reproducible CI.
