# CAAIF Core — One-command validation & release-readiness review

This additive tooling is for the **CAAIF Core SDK development tree**, not the earlier Sales/Finance research project. It never edits `caaif_core` or existing tests. It is not an official certification.

## Install

Extract `CAAIF_Core_Release_Validation_Addon.zip` into the existing CAAIF Core project root (with `caaif_core/`, `sdk_tests/`, `examples/`). Then, from that root, run:

```bash
.venv/bin/python tools/validate_release.py --mode full --out validation_reports/latest
```

Results are saved as `validation_reports/latest/report.md` (human-readable), `report.json` (machine-readable), `operation_profile.json`, and a `logs/` directory. Use `--mode quick` for a shorter check without the quantitative benchmark. A first run may take a few minutes. Each check has a timeout (default 90 seconds), and timed-out worker processes are stopped. No API keys or external AI services are required for the core distributed demo or benchmark. Optional real-framework validation needs `langgraph` and `agent-framework-core` installed. Schema validation needs `jsonschema`.

The command returns exit code **0 only when every required executable check has passed**; a skipped required check fails validation. Passing **does not** mean the public release is approved: legal, packaging, interoperability and security review items remain open until separately addressed.

If `.venv` is missing, use `python3 tools/validate_release.py ...` with the interpreter containing the project's optional dependencies. To change benchmark intensity: `--runs 20 --warmup 5`. A quick check: `.venv/bin/python tools/validate_release.py --mode quick --out validation_reports/quick`.

## Included gates

1. Release-validator self tests, Core source inventory and SDK regression suite (`sdk_tests`).
2. Three-agent reference-profile fixtures (`tests/test_three_agent_profile.py`).
3. Schema fixture validation (`tests/validate_examples.py`, requires `jsonschema`).
4. Integrated multi-process Controller + independent Context Provider + workers smoke demo.
5. Integrated wire and operation-profile regression tests.
6. Real LangGraph + Microsoft Agent Framework smoke demo when both packages are available; otherwise required validation reports SKIP.
7. Integrated HTTP-body/request-wire benchmark (full mode) with post-workflow revocation test and operation-level accounting.
8. Non-automated public release gates: license/provenance, installable packaging, security policy, contributor governance, CI, and independent security/performance evidence.

## Interpretation

Benchmarks use deterministic loopback processes. The `publication` operation sends synthetic context, `provider_read_and_auth` combines remote read and in-provider policy authorization, `worker_dispatch` invokes agents, and `callback_retrieval` retrieves context via the relay. Request-wire bytes include HTTP request headers; response bytes represent **body only**. Response headers, TCP/IP frames, TLS, WAN, real model tokens and an equivalent-control A2A implementation remain unmeasured.

**Never claim CAAIF is faster than A2A from these results.** Reference-based sharing may increase transfer/latency for small contexts. Real publishing of unnecessary context can dominate transferred bytes. A release candidate requires documentation, an installable package, security review, and fair baseline measurement.

## Privacy and operational notes

No credentials are printed, and logs apply limited token redaction. Nonetheless review local logs before publishing; test logs may include synthetic payloads. Git-ignore `validation_reports/`, and don't commit `.venv/` or secret material. The executable validation script does not access production services. It starts local processes via the existing examples and benchmark code.

## Expected report headline

`CAAIF VALIDATION PASS | PUBLIC RELEASE REVIEW OPEN` means technical tests passed and the resulting report lists unresolved release gaps. Anything else requires inspection of `report.md` and the logs.

## Optional GitHub Actions

The add-on includes `.github/workflows/caaif-validation.yml`: quick validation on pushes and pull requests, plus a selectable full benchmark on a manual workflow dispatch. It uploads the report as a CI artifact. This CI starter needs review and pinned dependency versions before formal public release. No GitHub repository is created or changed by this package.
