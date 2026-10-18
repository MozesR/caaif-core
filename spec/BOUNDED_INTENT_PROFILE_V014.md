# CAAIF v0.14 — bounded and data-derived intent (experimental)

**Status:** additive research implementation on `research/v014-bounded-intent` only. The protected `v0.1.0rc1` tag and `main` are unchanged; no public release or license is granted. This is not a stable protocol or production security specification.

## Problem and security invariants

Exact-parameter `TrustedIntent` in v0.12/v0.13 could prevent unapproved model deviations but could not capture tasks where a Reasoning Agent discovers parameters from retrieved evidence after the user initiates work. An LLM-produced interpretation of user language is **not** independent authority. A payment invoice can provide evidence for the amount, but must not grant permission to pay an attacker.

CAAIF v0.14 separates **authority to propose within a bounded envelope** from **approval to execute exact data-derived values**. The application host is a trusted authority **only after** it independently authenticates the user or identifies the applicable approved service policy. A host that merely accepts model-generated `approval_source` or UI text destroys this boundary.

1. The **Trusted Host** registers an immutable envelope with action, resource, purpose, context versions, parameter constraints, provenance of initial approval and expiration. An agent cannot create, broaden or relabel it.
2. The **Reasoning Agent** may choose values not fixed in the original request, but its proposal has zero authority by itself.
3. The **Parameter Validator** checks every field; absent or additional fields deny. Rules are intentionally small, deterministic and sandboxed; no arbitrary policy-code execution from a model payload.
4. For any parameter requiring external truth, a host-installed `trusted_lookup` resolver reads an authoritative source and returns `VerifiedParameter` with source ID/version. A resolver's identity, query and tenant isolation are the host's responsibility; a model's citation does not count as proof.
5. When `requires_confirmation=True`, the **Trusted Host** records exact-value approval **after the proposal**; it must show the user canonical action, resource, beneficiary and amount (or use an already approved workflow-specific service policy). A natural-language summary alone is not sufficient. Neither a model nor a source document may call the host-only confirmation route.
6. The independently configured action policy, contract, profile role, provenance, active versions and confirmation are rechecked at authorization, dispatch and tool use.
7. The distributed **Tool Gateway** cannot issue permits. It obtains an opaque one-time reference and asks the Controller online to validate and atomically consume it immediately before invocation. Controller/Provider failures fail closed. A consumed permit is not retried after unknown effects.

**Outside present guarantees:** Actual user reauthentication/confirmation UX, cryptographic approval attestations, sound LLM taint tracking, autonomous evidence-to-authority promotion, production gateway isolation, all four distributed role edges, durable multi-node authorization/replay, private-data egress mediation, WAN/TLS or real-model safety testing.

## TrustedIntentEnvelope JSON shape (experimental API)

This example permits the model to choose *a bounded amount*, while the account number must agree with a trusted supplier registry and the precise action still requires approval after proposal:

```json
{
  "intent_id": "payable-001",
  "correlation_id": "workflow-001",
  "action": "payment.prepare",
  "resource": "supplier:approved-17",
  "purpose": "invoice-payment",
  "context_refs": [{"ref":"ctx:invoice-001","version":"v1","scope":"workspace.instructions"}],
  "approval_source": "structured_user_action",
  "approval_reference": "host-ui:approved-envelope-77",
  "requires_confirmation": true,
  "parameter_constraints": {
    "amount": {"kind":"decimal_range", "minimum":"0.01", "maximum":"5000.00"},
    "currency": {"kind":"one_of", "values":["EUR"]},
    "beneficiary_iban": {"kind":"trusted_lookup", "resolver":"supplier-iban", "source_id":"master:supplier-17"},
    "mode": {"kind":"exact", "value":"prepare-only"}
  }
}
```

### Rule semantics

| Rule kind | Semantics | Invalid input behavior |
|---|---|---|
| `exact` | Canonical JSON structural equality; no coercion | Deny |
| `one_of` | Canonical membership in an explicit bounded set | Deny |
| `decimal_range` | Finite decimal **strings**, inclusive min/max (up to two decimal places in current prototype) | Deny floats, booleans, NaN, infinity, excess amount |
| `trusted_lookup` | Candidate equals `VerifiedParameter.value` from a host-installed named resolver, with a source ID/version | Fail closed for unknown/unavailable resolver or mismatch |

Unknown kinds, overly large constraints, missing parameters and extra parameters are rejected. A trusted lookup is not an attestation of user consent; it establishes a source-dependent expected value under trusted resolver code. The present SDK calls resolvers at each authorization check and rejects changed data, but does not atomically lock the source through a downstream effect.

## API and event sequence

```mermaid
sequenceDiagram
    participant U as User / Trusted Host UI
    participant H as Host Intent Authority
    participant R as Reasoning Agent
    participant C as CAAIF Controller
    participant V as Verified Data Source
    participant T as Task Agent
    participant G as Tool Gateway
    U->>H: Authenticate and approve bounded intent
    H->>C: register_bounded_intent(approved envelope)
    R->>C: propose_effect(derived exact parameters)
    C->>V: validate constraints / trusted lookup
    V-->>C: VerifiedParameter(value, source, version)
    H->>C: confirm_proposal(exact values; authenticated UI)
    H->>C: authorize_effect(proposal)
    C-->>T: opaque v0.14 permit (via authorized dispatch)
    T->>G: action_request + opaque permit
    G->>C: introspect AND consume permit
    C->>V: recheck current context / policy
    C-->>G: active, exact authorized action and source references
    G->>G: verify provider reads and registered tool
    G-->>U: Authorized tool result (egress control separately required)
```

The `approve` operation shown is a host responsibility; the prototype cannot prove a user clicked through a real UI. The HTTP example's bearer credentials are fixed per ephemeral localhost service and **do not establish production user or workload identity**.

## Controller-only opaque reference permit

For v0.14's online profile, an opaque random reference is mapped to one stored Controller permit. No JWT/HMAC verification key is shared with the Tool Gateway; it must authenticate and call `/introspect` with the candidate `action_request` and its subject. The Controller checks current context, proposal, contract, intent, confirmation, policy, expiration, purpose, exact parameter digest and replay, and atomically consumes the reference under its local process lock.

A Controller restart loses those authorizations; an unknown tool outcome must be reconciled and never retried automatically. A production deployment needs durable, multi-node-consistent single-use semantics or an equivalent receiver-side idempotency and reconciliation protocol. The Controller's access token is not a workload identity standard.

The v0.13 signed HMAC reference remains in `distributed_guard_v013.py` **only for backward-compatible historical research experiments**; use the v0.14 module for the new online-opaque research path. This does not silently replace existing v0.13 clients.

## Four-edge requirement: still open for distributed Guarded Profile G

The CAAIF Core Three-Agent reference profile defines four authorized edges: C→R `intent.assess`, R→T `task.execute`, T→R `task.report`, R→C `response.compose`. The local core tests the graph; the new distributed prototype focuses on independently protected R→T effects. The full distributed Controller mediation for the other three edges and tamper-resistant recipient delivery is **not implemented**. A network-connected agent could bypass an unenforced return path; clients must not claim full guarded-profile conformance yet.

Similarly, `authorize_disclosure()` checks the host-declared source lineage but cannot prove complete data provenance through arbitrary LLM transformations, and the return path is not physically forced through a gateway. Add trusted lineage capture and mandatory egress controls before production claims.

## Usage, tests, and reproducibility

- `python -m unittest discover -s sdk_tests -p 'test_intent_v014.py' -v`: 23 local bounded-intent tests.
- `python -m unittest discover -s sdk_tests -p 'test_distributed_guard_v014.py' -v`: 13 six-process HTTP tests.
- `python examples/sdk_guarded_distributed_v014_demo.py`: deterministic full-path demo.
- `python tools/run_sdk_tests.py --timeout 75`: SDK regression harness, including 12 original and 2 added independent modules.

This is an experimental **additional profile**, not an approval to release open source or to deploy in a regulated environment.
