> **Internal RC1 notice:** This document originated in an earlier SDK/release-preparation draft. For protected effects, the v0.13 guarded trust specification overrides any older wording about model-issued trusted decisions. Public publication requires the explicit release approvals described in `docs/RC1_RELEASE_STATUS.md`.

# Public API — provisional developer preview

The stable public API surface is **not finalized**. This is a reference to the interfaces implemented in the current research SDK; it is not a guarantee of backward compatibility.

- `caaif_core.LocalController`: in-process contract/policy enforcement and context registration/dispatch; see docstrings and `sdk_tests/test_local_sdk.py`.
- `caaif_core.AgentHandle`: process-local identity token; **not** remote workload authentication.
- `caaif_core.Denied`: a structured denial signal in local code.
- `caaif_core/adaptive_context.py`: adaptive transfer decision support.
- `caaif_core/context_reuse.py`: versioned reuse and delta demonstration.
- `caaif_core/http_transport.py`: experimental HTTP adapters.
- `caaif_core/remote_provider_v09.py`: experimental remote context provider/client.
- `caaif_core/provider_dispatch_v010.py`: research Controller/Provider integration.

Do not claim an A2A extension has been standardized or production-certified. API docs must be generated from reviewed function signatures before the first stable tag.
