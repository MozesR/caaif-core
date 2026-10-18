# Threat model — initial developer preview

**Assets**: trusted agent identity; interaction contracts and decisions; scoped context; context versions; credentials; tool execution rights; event/audit trail; optional cached content.

**Trust boundaries**: user/app → Conversational Agent; agent runtime → CAAIF Interaction Controller; Controller → Context Provider; agent → tool/runtime; local demo ↔ external transport.

| Threat | Required mitigation | Preview evidence gap |
|---|---|---|
| Caller spoofing / caller field substitution | Bind identity to authenticated transport or verifiable workload credential; deny on mismatch | HTTP demo does not establish workload authentication |
| Contract bypass / direct agent-to-task execution | Enforce authorization at dispatch AND tool boundary | Real framework-to-tool bypass not exhaustively tested |
| Prompt injection in retrieved context | Treat retrieved content as data; enforce policy outside LLM | No red-team suite with real LLMs |
| Stale or revoked context / cache | Retrieval-time authorization, version checks, cache invalidation | Race conditions under WAN/concurrency not proven |
| Cross-scope or cross-tenant data leakage | ABAC and tenant-bound references, reject wrong scope, prove isolation | No production multi-tenant hardening |
| Replay/duplicate side effects | Idempotent downstream operations and reconciliation | Core SDK does not guarantee exactly-once execution |
| Spoofed evidence / forged reasoning decision | Trusted decision binding with verifiable provenance | Real-world identity trust chain not proven |
| MITM and transport tampering | TLS/mTLS with rotation and certificate validation | Loopback only |
| DoS / resource exhaustion | Bounded payloads, quotas, timeouts, admission control | Load and hostile network tests incomplete |
| Supply-chain compromise | Pin vetted dependencies and GitHub Actions; scan build outputs, use provenance | External review/SBOM pending |

**Release rule**: 'developer preview' wording only, no enterprise/production security assurances without separate independent assessment.
