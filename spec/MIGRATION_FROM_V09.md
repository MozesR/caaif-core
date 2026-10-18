> **Status: historical architecture draft.** For effectful work, the guarded trust boundary in `spec/TRUST_ARCHITECTURE_DRAFT3.md` and `spec/GUARDED_DISTRIBUTED_PROFILE_V013.md` supersedes any assumption that an LLM-produced decision is an authorization. This is a developer preview, not a stable security standard.

# Migration Path from CAAIF Research Prototype v0.9.x

**Do not replace the existing code immediately.** Freeze the tested prototype and make the new core in a separate repository/project namespace.

| Current v0.9.x component | Proposed destination | Migration action |
| --- | --- | --- |
| Sales/Finance-specific controller | `examples/credit-review/` | Keep solely as example and end-to-end regression fixture |
| `collaboration.json` | `contracts/` | Extract generic contract fields, retaining business policies only in the example |
| HTTP routing and authentication | `adapters/http/` + `security/` | Standardize identity binding; no shared cross-service token loading |
| `finance_batch.py` | core dispatch optimization / optional workflow adapter | Preserve atomic admission but avoid encoded Sales/Finance states in the core |
| `state_adapter.py`, `persistence.py`, `durable_controller.py` | `extensions/persistence-sqlite/` | Optional implementation; document in-memory limitations |
| `execution_ledger.py`, `reconciliation.py` | `extensions/idempotency/` and `extensions/reconciliation/` | Keep receiver-side effect handling and fail-closed uncertainty |
| `recovery_coordinator.py`, fencing | `extensions/recovery/` | Not needed for Hello World; independently gated and tested |
| HTTP tracing benchmarks | `benchmarks/legacy/` | Retain numeric history with clear caveats; add context/token benchmarks |
| Policies | `adapters/policy/` | Define pluggable interface; sample deterministic evaluator and optional OPA adapter |

## Ordered migration

1. **Tag/freeze:** archive a snapshot of working v0.9.x; run regression suite; record current observed outputs.
2. **Extract canonical objects:** interaction request, contract, context ref, decision and result, all business-agnostic.
3. **Minimal local controller and three generic reference roles:** demonstrate Conversational → Reasoning → Task and result return, without a required DB or external gateway. Add a two-agent core-only example to validate optionality.
4. **Introduce A2A adapter:** map CAAIF interaction metadata and contracts without forking A2A.
5. **Build governed deployment profile:** independent gateway, transport identity, deny-by-default policy, context scope enforcement.
6. **Validate the Three-Agent Reference Profile:** role/identity binding, prohibited bypass, trusted Reasoning decision, independent Task/tool authorization and minimal context at each handoff.
7. **Reintegrate optional reliability extensions:** only after reusable extension interfaces and conformance fixtures exist.
8. **Benchmark and publish draft:** full governance-equivalent baseline, repeated context, real model tokens, security tests.

**Avoid:** translating business-specific workflow states into normative CAAIF state names. CAAIF states describe interaction admission and outcomes, not Sales/Finance business state.
