# CAAIF Core - Security and Trust Architecture Revision

**Draft:** `1.0.0-draft.3` | **SDK add-on:** v0.12 | **Status:** proposal and local proof of concept, **not** an approved production standard

## 0. Why this revision exists

The 18 October 2026 technical review identified a genuine security gap: an LLM-originated Reasoning Agent could produce a valid-looking decision record when exposed to prompt injection. The earlier profile checked a matching role, contract, reference and deadline, but did not prove the action was justified by independently authenticated intent. This draft resolves that *architectural* confusion. It does not claim to solve prompt injection universally.

**Central rule:** *An agent-generated decision is a proposal, not a source of authority.* All protected effects require authorization from a trusted application authority and an independently evaluated policy over the exact requested action, resource, parameters, purpose, principal and current context restrictions. The tool gateway must enforce again before the side effect.

The Six CAAIF Core responsibilities remain: principal binding; contract resolution; independent policy decision; controlled context access; dispatch; redacted observability. The optional Three-Agent Reference Profile retains Conversational -> Reasoning -> Task -> Reasoning -> Conversational. No new required fourth agent is introduced.

## 1. Trust boundaries and authority sources

| Boundary | May do | Must not do |
|---|---|---|
| User/application gateway | Authenticate originating user/app; register bounded trusted intent with host approval | Treat retrieved content or unverified role strings as user intent |
| Conversational Agent | Clarify and propose intent; present sanitized results | Authorize protected execution |
| Reasoning Agent | Produce plans and execution *proposals* using evidence | Create grants/permits; self-approve purpose/resource/parameters |
| CAAIF independent control plane | Bind authentic principal, resolve contract, evaluate trusted intent and policy, issue bounded execution authorization | Depend on the model's `authorized: true` flag |
| Context Provider | Return authorized projections with trusted metadata and current policy | Promote source content into privilege or treat a `context_ref` as a bearer credential |
| Task Agent | Perform the authorized task by invoking an isolated tool gateway | Bypass the gateway or broaden an action |
| Tool gateway | Verify action-specific grant at time of use; apply downstream control/idempotency | Trust a model-generated reference without checking audience, action and parameters |

**Authority roots for a guarded distributed deployment:** authenticated workload identity; approved and integrity-protected policy/contract registry; trusted user/application intent binding; trusted context-ingestion/provenance metadata; tool-gateway authorization. The Reasoning Agent is not one of these authority roots.

### Security profiles

- **Local Research Profile (implemented):** bound object handles and opaque in-process permits; protects against modeled agent misbehavior but **not malicious code inside the same Python process**. A local handler with unrestricted filesystem/network access can bypass the boundary.
- **Guarded Deployment Profile (specified only):** separate security principals and network controls, a trusted contract/policy administration process, isolated Context Provider, mTLS or equivalent, sender/audience-bound authorization, downstream tool enforcement, durable nonce/idempotency state, revocation and audit. Not yet implemented or penetration tested.

## 2. Protected execution lifecycle

1. **Verified intent registration.** Trusted host code authenticates the initiating principal and records `{intent_id, correlation_id, action, resource, exact protected parameters, purpose, allowed context refs, deadline}`. Source text cannot register or change this record.
2. **Evidence ingestion.** Context Provider assigns provenance, trust label, sensitivity, allowed purposes/recipients/actions, immutable version, and lineage outside the model.
3. **Untrusted proposal.** Reasoning Agent submits `{intent_id, action, resource, parameters, purpose, context refs}`; it never signs or issues an authorization.
4. **Independent policy decision.** Controller compares proposal to trusted intent, resolves the active contract, verifies authenticated principal, current context version/provenance/revocation, then calls a deterministic trusted policy decision function. Deny by default.
5. **Action-bound permit.** Successful decision issues an opaque locally stored authorization bound to actor, exact action/resource/parameter digest, contract and policy versions, correlation, purpose, context versions, recipient, tool-gateway audience and short deadline.
6. **Independent dispatch and tool enforcement.** Every protected Task dispatch verifies the permit. The registered trusted tool gateway verifies it again and uses only registered action handlers, not arbitrary model-provided callbacks.
7. **Output disclosure check.** Before releasing derived information, evaluate the conservative union of source restrictions: classification maximum, allowed recipient/purpose intersection, and recorded lineage. This assumes trustworthy lineage capture; untracked output cannot be safely declassified.
8. **Auditable outcome.** Log redacted IDs and reason codes. An ambiguous side effect remains blocked pending reconciliation; do not silently retry.

Every one of the four Three-Agent role edges MUST pass independent contract and principal checks, including the two return edges. The Reasoning -> Task effect edge requires the additional protected execution sequence.

## 3. Reference objects and binding requirements

`TrustedIntent` is issued by the verified host, not by an LLM. `ActionProposal` is authored by an untrusted agent and is non-authoritative. `ExecutionAuthorization` is issued by the independent control plane.

**Required authorization bindings (Profile G):** issuer identity and trust domain; subject principal; task recipient; tool gateway audience; action; resource; canonical parameters digest; purpose; context references/versions; contract identifier/version; policy version; initiating intent ID; expiry/not-before; unique nonce or idempotency binding; revocation state; authenticated or sender-constrained presentation.

An opaque in-process `permit:local/…` reference is implemented in the demonstration. **It is not a JWT, signed credential or sender-constrained network token.** For a future distributed binding, prefer established workload identity and authorization technology (SPIFFE/SPIRE, OAuth token exchange, downstream policy engines) over inventing a cryptographic token format. A 30-second TTL is illustrative; distributed designs must specify maximum clock skew, fail-closed behavior when clocks are unreliable, and revocation propagation SLOs. Never imply zero-latency revocation in a replicated system.

## 4. Provenance, information flow and data minimization

Every context version used for protected execution MUST carry trusted metadata assigned by an ingestion authority, including:

`source_id`, `origin_trust`, `classification`, `allowed_purposes`, `allowed_recipients`, `allowed_actions`, `derived_from`, `context_version`, `policy_version` and owner/tenant binding in distributed deployment.

The current add-on implements trusted local labels, action checks, and conservative merge for derived classifications/allowed destinations. It **does not** implement sound information-flow tracking through arbitrary LLM transformations. Model-generated citations or provenance metadata alone are not trustworthy. A protected application's egress path MUST pass through an enforceable output gateway with trusted lineage or block uncertain disclosure.

**Two independent optimizations:** (a) authorized field-level projection determines *what* may be disclosed, (b) inline/reference/cache/delta selection determines *how* permitted data is transported. Security first: cache hits and references never bypass current authorization.

## 5. Identity, contracts and policy administration

- Contract identities/versions are installed by trusted administration. A network binding MUST authenticate contract authors or use a signed trusted registry, protect against downgrade, and reject unknown versions.
- Action policy must independently evaluate principal, action, resource and request context, comparable to the XACML PEP/PDP/PIP/PAP separation or Cedar's PARC model; CAAIF does not require a new policy language.
- The trusted host supplies intent only after user/application identity, consent and context are verified; Reasoning Agent output cannot mutate the trusted record.
- Enforcement requires no direct credential or network path from Task to protected resources except the tool gateway. LLM prompts alone do not provide this guarantee.

## 6. A2A and MCP interoperability

CAAIF should be an **interaction/authorization semantics layer** that can be carried as an A2A extension, not an alternative mandatory messaging protocol. A2A can supply discovery, task messaging and lifecycle; CAAIF adds independently enforced intent binding, context disclosure policy, and tool-action authorization requirements. MCP continues to mediate resource/tool calls; the tool gateway checks the CAAIF action authorization **plus** the destination tool's own policy. Externally test the extension against compliant A2A implementations before claiming interoperability.

## 7. What the code in this add-on actually demonstrates

`caaif_core/guarded.py` adds `GuardedLocalController` as an **opt-in, fail-closed local research implementation**. It disables the inherited `issue_decision(...authorized=True)` pathway, registers intents only through an injected trusted-host handle, treats Reasoning requests as untrusted proposals, binds opaque permits to specific actions and parameter digests, re-evaluates independent policy at dispatch/tool use, and routes tool execution to trusted registered handlers. It also enforces basic source labels and output disclosure checks *when the host routes egress through the guard*.

The earlier `LocalController` and its legacy `issue_decision` remain available for backwards-compatible research examples and **must not** be presented as a secure authorization system. The opt-in guarded class is not wired into the separate v0.10 HTTP Context Provider or into all adapters yet. A production claim requires such integration plus actual network/service isolation.

## 8. Pre-registered falsifiable evaluation plan

These are **proposed study thresholds, not observed results**:

| Question | Proposed falsifiable hypothesis | Experiment / acceptance measure |
|---|---|---|
| RQ1 trust boundary | No protected action executes from LLM-generated decision alone | >= 200 adversarial prompt-injection trials with zero successful policy bypasses; report Wilson interval, false-denial rate and task quality |
| RQ2 disclosure efficiency | For >= 4 reused large contexts, authorized projection cuts excess disclosed fields by >= 50% vs an equivalent-control handoff at equal task accuracy | Publish/full context vs selective inline vs references/delta, include ingress/auth/egress and model tokens |
| RQ3 framework independence | Same contracts and enforcement outcomes work with unmodified native runtimes via external adapters | LangGraph, Microsoft Agent Framework, A2A-compliant external runtime; no modifications to framework internals; adapter complexity documented |
| RQ4 guarded deployment | Replay, expired grants, role spoofing, revoked data, tool bypass and tenant crossing never succeed in defined network tests | Authenticated separated deployments; p95 revocation propagation target, concurrency and WAN/TLS data; third-party adversarial review |

Measure unnecessary recipient exposure (fields/bytes beyond task need), unauthorized side-effect success, false-denial rate, legitimate task success, tokens, p50/p95/p99 latency, publication, policy calls and total bytes. Report hardware/OS/Python/framework versions, sample sizes, intervals, and complete fixture/benchmark scripts. Existing localhost savings are not evidence of A2A superiority.

## 9. Concrete release gates

**Block production/public security claims** until: guarded real HTTP deployment, signed/trusted identity and policy contracts, downstream enforcement and bypass-negative tests, replay/revocation semantics across nodes, independent prompt-injection testing, and release-security review. A public **experimental developer preview** may be appropriate only with explicit scope/limitations and license/provenance approval.

## 10. Revision map from the 18 October review

- Trust gap: Reasoning decision -> untrusted proposal + verified intent + independent permit.
- Information-flow gap: host-assigned provenance, conservative derived restrictions and egress decision interface.
- Permit ambiguity: explicit binding, nonce, expiration, policy version, replay/recipient checks (local proof only).
- Related work: references to CaMeL, access-control policy architecture, A2A, SPIFFE and OAuth in documentation.
- Weak evaluation: pre-registered hypotheses, primary information-exposure metrics, equal-controls baselines and reproducibility plan.
- Naming/diagram consistency: four role edges, correct permit direction, distinct enforcement boundaries.

## References (public background)

- Debenedetti et al., *Defeating Prompt Injections by Design* (CaMeL), 2025: https://arxiv.org/abs/2503.18813
- Cedar Policy Language, authorization request (principal/action/resource/context): https://docs.cedarpolicy.com/auth/authorization.html
- SPIFFE workload identity and SVIDs: https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/
- Agent2Agent protocol extension model: https://a2a-protocol.org/dev/topics/extensions/
- IETF RFC 8693, OAuth 2.0 Token Exchange: https://www.rfc-editor.org/rfc/rfc8693
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
