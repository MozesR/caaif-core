# CAAIF v0.14 — implementation evidence and unresolved controls

**Basis:** RC1 developer-preview source copied from version tag `v0.1.0rc1`, with additive source changes in `research/v014-bounded-intent`.
**Scope:** deterministic local Python and six-service localhost regression tests; not a security certificate.

## Implementation delta

1. `caaif_core/intent_v014.py`: bounded declarative parameter rules, decimal-string validation, independent trusted-resolver result type, deny-by-default rule checks.
2. `caaif_core/guarded.py`: `register_bounded_intent`, `register_trusted_parameter_resolver`, `confirm_proposal`, and `revoke_confirmation`; authorization, dispatch and tool execution revalidate active constraints/confirmation.
3. `caaif_core/distributed_guard_v014.py`: online random opaque permits, Controller-only issuance, atomic single-use introspection, no shared signing key in the Gateway's v0.14 authorization path.
4. `examples/sdk_guarded_distributed_v014_demo.py`: six separate localhost processes using intent envelope and exact after-proposal confirmation.
5. `sdk_tests/test_intent_v014.py` and `test_distributed_guard_v014.py`: 36 new negative and positive tests.
6. `spec/BOUNDED_INTENT_PROFILE_V014.md`: threat assumptions, mechanism, trade-offs and explicit missing assurance.

## Local test evidence

| Check | Result | Meaning / limitation |
|---|---|---|
| v0.14 bounded-intent local regression | **23 / 23 passed** | Synthetic amount/range/beneficiary/confirmation checks; no real approval UX |
| v0.14 distributed-loopback regression | **13 / 13 passed** | Six independent OS processes, token consumption and adversarial input; no hostile network or mTLS |
| Original 12 SDK regression modules | **161 / 161 passed** | Existing source behavior retained in local test environment |
| **Combined independently completed SDK modules** | **197 / 197 passed across 14 modules** | The aggregate runner invocation was interrupted after 11 modules by the container timeout; the three remaining modules passed separately, so this is **not** a claim that one continuous full runner completed |
| Three-Agent profile tests | **15 passed** | Structural/contract checks for local core |
| Schema fixtures | **14 objects valid** | No semantic security guarantee |
| Release-preparation tests | **9 passed** | Engineering checks only |
| Release approval gate | **BLOCKED, intentionally** | No active license or signed public-release approvals |

The GitHub Actions pipeline should independently run `tools/run_sdk_tests.py`, profile/schema/release checks, and package build after pushing the branch. Record the actual remote CI outcomes separately; do not assume they have passed in advance.

## Reviewer request → response → remaining gap

| Review priority | Implemented | Remaining |
|---|---|---|
| TrustedIntent provenance | Host-authorized bounded envelope, explicit approval source/reference, immutable stored constraints | Actual authentication/UX proof, malicious/buggy host protection |
| Data-derived values | Decimal ranges + independent trusted lookups, full field set validation | Value-level taint tracking, trustworthy ingestion, policy-derived dynamic subdelegation |
| Human confirmation | Host-only post-proposal exact-value confirmation + revocation | UI showing canonical details and cryptographic approver binding |
| Gateway permit separation | Online opaque reference; no shared HMAC signing secret in v0.14 path | Distributed durable consumption, workload identity, network bypass isolation |
| Legitimate task utility | Deterministic successful preparation under constraints | Real-model task completion and false-denial measurement |
| End-to-end disclosure | Existing host-invoked lineage guard unchanged | Mandatory trusted egress, all distributed return edges, declassification model |
| Comparable research | Explicit research hypotheses and baselines proposed | AgentDojo/equivalent-control A2A real experiments, cost/token accounting |

## Explicit **non-claims**

- **No** production-grade security or autonomous payments. The payment fixture is a **preparation-only synthetic registered tool**, not a banking integration.
- **No** proof that any user was truly authenticated: host-only methods and mock bearer tokens provide a development security boundary, not a real user-approval ceremony.
- **No** claim that 0 test bypasses equals zero real prompt-injection risk.
- **No** proof of complete provenance/taint tracking of model outputs or mandatory egress mediation.
- **No** fair performance claim versus A2A, CaMeL, FIDES, Progent or IsolateGPT.
- **No** changes to ownership, licensing or the public-release decision.

## Next experiment gates

- Wire a real authenticated confirmation UI into the trusted host; capture authenticated principal and exact displayed canonical values independently of the model.
- Support trustworthy source integrity and freshness when dynamic parameters are resolved; test concurrent data changes and stale approvals.
- Make all four distributed Three-Agent edges pass an independently authenticated enforcement boundary, with physically constrained routing.
- Build an obligatory egress/derived-output lineage boundary; define declassification and side-channel threat model.
- Establish durable replay/idempotency through crash and multi-gateway race tests; eliminate static keys in favor of workload identities.
- Run AgentDojo with actual model agents. Report benign utility, attacker success, false-denial, excess disclosure, tokens and confidence intervals alongside equivalent-control baselines.
