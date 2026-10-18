# Current implementation versus production requirements

| Control | v0.12 state | Required next evidence |
|---|---|---|
| Independent trusted intent | Local host object identity; immutable intent record | Authenticated originating user/app identity and approval evidence |
| Reasoning decision treated as proposal | Guarded local code and tests | Native LangGraph/Microsoft integration in guarded mode |
| Action/resource/parameters binding | Opaque in-process permit with canonical JSON hash | Sender-constrained authenticated permit with trusted issuer/audience |
| Replay and expiry | In-memory request/permit guard; fail-closed unknown outcome | Durable multi-instance nonce/idempotency, clock-skew handling |
| Context provenance | Trusted local labels; conservative merge | Remote provider, policy-signature trust, end-to-end information flow |
| Tool boundary | Registered trusted local tool action; no arbitrary callback | Physically isolated MCP/tool gateway and enforced network paths |
| Output disclosure | Host-invoked coarse provenance release check | Trusted lineage capture, full egress mediation, declassification process |
| Revocation | Context revocation, permit revocation, policy rotation | Distributed revocation delivery/acknowledgment SLO and race tests |
| Security tests | Synthetic local test cases, not real models | AgentDojo-style attack suite, hostile network, external review |
| Comparative efficiency | Earlier loopback studies only | Equivalent-security A2A control baseline, tokens, representative tasks |

**Migration:** retain draft.2 for current research and run new guarded profile in parallel. Treat the old `authorized=True` path as deprecated for protected effects. Do not silently change existing user APIs or claim the guarded network stack exists. When deploying protected actions, restrict all direct tool credentials and network routes to the gateway.
