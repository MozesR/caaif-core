> **Status: historical architecture draft.** For effectful work, the guarded trust boundary in `spec/TRUST_ARCHITECTURE_DRAFT3.md` and `spec/GUARDED_DISTRIBUTED_PROFILE_V013.md` supersedes any assumption that an LLM-produced decision is an authorization. This is a developer preview, not a stable security standard.

# Proposed A2A Adapter Mapping — CAAIF Core v1.0 Draft

**Status: design proposal; NOT an official A2A extension.** Follow the exact A2A version negotiated by the peers. The extension URI below is a placeholder, not a published identifier.

| CAAIF concept | Proposed A2A integration |
| --- | --- |
| Recipient discovery | Existing A2A Agent Card, skill declarations, supported interfaces |
| Capability | Agent skill ID or contract-specific capability reference; exact mapping configured by adapter |
| Request | A2A SendMessage with structured content, plus CAAIF metadata under an extension namespace |
| Request correlation | Preserve A2A task/context IDs; add CAAIF `request_id` only where it has different idempotency semantics |
| Permit / interaction decision | Out-of-band trusted policy decision and authorization; do not treat arbitrary A2A metadata as a permit |
| Result | A2A task outcome or artifact plus CAAIF decision/outcome audit metadata |
| Context references | CAAIF metadata pointing to controlled context-provider references; no unrestricted dereferencing |
| Capability negotiation | Declare an A2A `AgentExtension` in the Agent Card; activate only after peer agreement |
| Tool calls | MCP and other tool adapters invoked by the recipient subject to separate tool authorization |

When the **Three-Agent Reference Profile** is enabled, its routing and role constraints are enforced by CAAIF adapters/gateways, not by relying on untrusted A2A Agent Card text or metadata. Reasoning decision references must resolve to trusted records. See `THREE_AGENT_PROFILE.md`.

## Proposal sketch

The future project should register an extension URI in an owned namespace. **For illustration only**:

```json
{
  "capabilities": {
    "extensions": [
      {
        "uri": "https://example.invalid/caaif/extensions/context-interaction/v1",
        "description": "CAAIF interaction contracts and scoped context references",
        "required": false
      }
    ]
  }
}
```

The actual extension schema should reference CAAIF's canonical `InteractionRequest` as a metadata payload while delegating transport mechanics to A2A. Do not require an extra redundant A2A message solely to ask for policy permission when the local adapter can authorize before send. Do not claim this proposal is wire compatible until demonstrated with a released A2A SDK and two independent implementations.

**Sources:** [A2A spec](https://a2a-protocol.org/v1.0.1/specification/), [A2A extensions](https://github.com/a2aproject/A2A/blob/main/docs/topics/extensions.md).
