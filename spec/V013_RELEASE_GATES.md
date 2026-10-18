# CAAIF v0.13 — Remaining Security Release Gates

**Public distribution as a security-enforcing production framework remains BLOCKED.**

1. **Workload identity:** replace static local tokens with authenticated workloads (SPIFFE/SPIRE or supported platform identity), least-privilege service credentials and signed policy configuration.
2. **Trusted registry and policy administration:** versioned, signed contracts; durable policy change records; verified provenance assigned by trusted ingestion, not model content.
3. **Gateway-bypass prevention:** network policy plus tool-system authorization must prevent direct access to protected effects outside the gateway.
4. **Permit interoperability:** standard token binding, audience/sender constraint, clock-skew rules, key rotation, durable replay/idempotency records, policy invalidation and revocation guarantees.
5. **Full Three-Agent integration:** mediate all four required edges and guard outbound return paths under distributed principal binding.
6. **Information-flow:** propagate origin, sensitivity, permitted purpose and disclosure labels across transformations and store/retrieve only minimum authorized projections.
7. **Security fault testing:** concurrent revocation races, process restarts, malicious peer services, replay across nodes, impersonation, tenant isolation, prompt injection by real models, downstream failure reconciliation.
8. **Network and protocol:** TLS/mTLS, hardened HTTP server, bounded concurrency and resource use, replay-resistant inter-service calls, A2A/MCP bindings where appropriate.
9. **Evidence:** independent security review and equivalent-control comparison; publication/ingestion, policy and execution cost all measured. No claim of universal attack immunity.
10. **Governance:** complete provenance/licensing review, vulnerability disclosure process, CI release gates and documented support scope.

The demo has no secret exfiltration tool installed. Its refusal of `email.send` does not prove that a real hosted LLM resists sophisticated prompt injection or that malicious code in the same OS user context cannot steal secrets.
