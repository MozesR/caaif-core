# CAAIF Distributed Guarded Profile — Working Specification v0.13

**Status:** Research-only, opt-in extension of CAAIF Core and its Three-Agent reference profile. Not a stable wire protocol.

## 1. Normative division of authority

- **Conversational Agent:** proposes user-facing intent and dialogue; it does not create trusted policy or execution authorization.
- **Reasoning Agent:** reasons over both trusted and untrusted context and submits a **proposal**. It does not possess the trusted-host, controller-signing, or gateway introspection credentials.
- **Task Agent:** submits an exact action request plus independent authorization to a registered gateway. It has no direct tool credentials.
- **Trusted Host / Intent Authority:** authenticates the application/user request and registers immutable intended action/resource/parameters/purpose/context references, along with provenance verified outside model text.
- **Interaction Controller / Policy Authority:** binds authenticated reasoning proposals to trusted intent, profile contract, provenance and independent policy; issues a constrained authorization only after all controls permit it.
- **Context Provider / policy enforcement point:** limits each read by authenticated actor, reference, scope, version, correlation, field grants and live policy.
- **Tool Gateway / final enforcement point:** authenticates Task, verifies authorization at execution, checks Controller and Provider freshness, and permits only registered operations.

An agent role string supplied in JSON MUST NOT be used as identity. A well-formed Reasoning record MUST NOT itself confer execution authority.

## 2. Prototype endpoints

| Endpoint | Principal | Effect |
|---|---|---|
| `POST /trusted/context` | trusted host | Registers independently verified provenance after provider publication |
| `POST /trusted/intent` | trusted host | Registers immutable host intent |
| `POST /proposals` | Reasoning worker | Stores an untrusted proposal; returns a proposal handle |
| `POST /trusted/authorize` | trusted host | Independently evaluates and creates an action-bound permit |
| `POST /introspect` | Tool Gateway | Checks active permit, live policy and provider availability |
| `POST /trusted/revoke` | trusted host | Revokes a permit from subsequent introspections |
| `POST /trusted/disclose` | trusted host | Separately checks source-lineage disclosure eligibility |
| `POST /execute` (Tool Gateway) | Task worker | Consumes an authorized permit and executes a registered tool at most once per gateway process |
| `/publish`, `/read`, `/revoke` (Provider) | authenticated provider actor | Existing independent field-scoped context operations |

All endpoints are localhost-only for the prototype, accept bounded JSON, and return structured denials without logging raw context, credentials or model reasoning.

## 3. Action-bound permit (experimental JSON signed envelope)

The prototype claim set includes `typ`, `iss`, `aud`, `sub`, `jti`, `reasoning_agent`, `contract_id`, `contract_version`, `intent_id`, `correlation_id`, `action`, `resource`, `parameters_hash`, `purpose`, `context_refs`, `policy_version`, `iat`, and `exp`.

A trusted Controller signs a canonicalized claim set using a shared HMAC key held by the Controller and Tool Gateway **only**. The Task worker receives the signed permit, never the signing key. The gateway checks signature, audience, bound task subject, lifetime, exact canonical parameter digest and proposal metadata, controller introspection, current provider read, and local single-use `jti` consumption. The authorization is not transferable to a different recipient, action or set of parameters.

**This signed format is a research fixture, not a standardized bearer/capability format.** An eventual production binding should use externally reviewed sender-constrained mechanisms, proper key management, rotation, replay storage and revocation dissemination.

## 4. Decision model

1. Is the authenticated principal allowed to invoke this endpoint? If not, deny.
2. Is the requested interaction declared in the Three-Agent Profile? If not, deny.
3. Does the proposal match a still-active trusted intent in action, resource, parameters, purpose, correlation and context references? If not, deny.
4. Do trusted provenance labels permit the operation and receiving Task? If not, deny.
5. Does the independent deterministic policy allow this exact proposal? If not, deny.
6. Is there an active and cryptographically verifiable, action-bound permit for the target Task/Gateway? If not, deny.
7. Is the same permit unused, unexpired, unrevoked, and current against Controller and Context Provider state? If not, deny.
8. Is the tool registered and the request byte-for-byte semantically bound to the permit? If not, deny.
9. Reserve the local `jti` and execute **once**. On an ambiguous result, do not automatically retry.
10. At outbound disclosure, independently check the declared source lineage and recipient/purpose. A missing lineage denies release through the guarded path.

A context reference is a **locator**, not an authorization grant. Cached information never bypasses reauthorization. Unknown or unavailable policy data results in denial.

## 5. What was verified and what was not

Verified in six independent localhost processes: endpoint actor binding; malicious data-induced proposal denial; independent Controller issuance; gateway action/parameter binding; scoped Provider reads, version changes and revocation; duplicate execution denial; trusted disclosure authorization and denial.

Not verified: production workload isolation, trust in arbitrary user-supplied intent, distributed multi-node replay safety, revocation SLA or instantaneous TOCTOU exclusion, security when model code can access operating-system secrets, arbitrary unauthorized network/tool paths, complete provenance propagation across LLM transformations, all four distributed profile edges through the new guarded boundary, A2A/MCP security and WAN/TLS/real-model adversarial performance.
