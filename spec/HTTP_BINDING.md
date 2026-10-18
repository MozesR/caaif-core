> **Status: historical architecture draft.** For effectful work, the guarded trust boundary in `spec/TRUST_ARCHITECTURE_DRAFT3.md` and `spec/GUARDED_DISTRIBUTED_PROFILE_V013.md` supersedes any assumption that an LLM-produced decision is an authorization. This is a developer preview, not a stable security standard.

# Illustrative HTTP Binding — NOT Required by CAAIF Core

The canonical protocol is transport-neutral. This binding sketches an HTTP adapter for testing. Implementations MAY combine the request and decision/dispatch into one round trip.

| Method | Path | Operation | Statuses |
| --- | --- | --- | --- |
| POST | `/v1/interactions` | authorize and dispatch (atomic admission before dispatch) | `200` completed; `202` running; `403` denied; `409` conflict; `400` malformed |
| POST | `/v1/interactions:propose` | policy decision only | `200` decision; denial body carries `status=denied` |
| POST | `/v1/interactions:dispatch` | dispatch previously permitted request | `200`, `202`, `403`, `409` |
| POST | `/v1/context:resolve` | access-time authorized projection | `200`; `403`; `409` version conflict |

Authorization is not guaranteed by any of these paths themselves. For Guarded Profile, use authenticated TLS peer identity, enforce caller-to-principal binding, restrict upstream bypass, check audience and time-to-live, and use a nonforgeable permit reference. Do not trust caller-supplied `caller_id` or `permit_id`.

**Example request:** `examples/request_ref.json`; **example permit decision:** `examples/decision.json`.

### Error model

Use structured error codes: `unauthenticated`, `not_permitted`, `unknown_contract`, `invalid_capability`, `context_scope_denied`, `context_version_conflict`, `permit_expired`, `permit_revoked`, `duplicate_conflict`, `policy_unavailable`, `outcome_unknown`, `recipient_unavailable`. Do not expose internal stack traces, private policy inputs, or secrets.

**No implementation is bundled** for these routes in this draft. Their final names and A2A mapping require interoperability review.
