# CAAIF Core SDK v0.11 — Integrated HTTP Measurement Add-on

This add-on leaves `caaif_core` and the existing demos unchanged. It measures the **actual v0.10 four-handoff scenario** using the same Three-Agent profile, with a trusted Controller/relay process, three independent worker processes, and an independent Context Provider process.

## Quick start

From your existing CAAIF Core SDK project directory:

```bash
unzip -n ~/Downloads/CAAIF_Core_SDK_v0.11_Integrated_Metrics_Addon.zip -d .
.venv/bin/python -m benchmarks.integrated_v011.compare --runs 20 --warmup 5 --large-bytes 18000 --out benchmarks/integrated_v011/results.json
.venv/bin/python -m unittest discover -s benchmarks/integrated_v011 -p 'test_integrated_wire_v011.py' -v
.venv/bin/python -m unittest discover -s sdk_tests -v
```

On Unix/macOS, no new dependencies beyond the existing SDK are needed for the benchmark.

## What is actually measured

The benchmark installs a tiny, **opt-in, benchmark-only HTTP client meter** in every participating process. It counts successful workflow HTTP calls, bytes passed to the HTTP socket by clients (including HTTP request headers and request bodies), bytes read as HTTP response bodies, and end-to-end four-handoff elapsed time. The metering file logs **only process roles, byte counts, and event types**; it does not log URL paths, tokens, credentials, user data, or context values.

Every run performs the following under the existing Core contracts:

1. Conversational Agent publishes intent to independent provider; Reasoning retrieves scoped `topic`.
2. Reasoning publishes instructions; Task retrieves scoped `topic` and performs authorized operation.
3. Task publishes receipt; Reasoning retrieves authorized points.
4. Reasoning publishes summary; Conversational retrieves authorized points.

The trusted controller enforces caller identity, contracts, policy and the Reasoning-issued decision. The independent provider enforces bearer identity, grants, version, scope, correlation and retrieval-time policy. A **revocation denial** is tested after each run, but is deliberately **excluded** from the reported successful workflow timing/byte counts.

Each normal run performs 20 client-originated HTTP requests: 4 publication, 8 provider reads (dispatch-time check and callback-time retrieval), 4 worker invokes, and 4 relay callback reads. This counts the component's current access model; **20 calls is overhead to study, not an efficiency improvement**.

Two fixture cases share the same authorized `topic`, but the large case additionally contains `--large-bytes` of private/irrelevant data in each of the four published contexts. The provider must never expose that private field to recipients. Because the full publisher sends it to the provider, **its publication cost is included**.

## What is not measured or proved

- HTTP **response headers** (only response bodies), TCP/IP framing, TLS, WAN latency, redirects/proxies, network congestion, or deployment cost.
- Token consumption, actual LLM inference, A2A protocol overhead, or real Microsoft/LangGraph execution in this benchmark.
- A like-for-like full-context or selectively-inlined baseline with equivalent policy and isolation. **Do not claim performance superiority over A2A from these measurements.**
- Real workload identities, production policy engine, and durable context storage.
- End-to-end network security: this remains loopback-only test infrastructure.

The benchmark results are repeatable research measurements, not a conformance certificate. Follow-up work: add equivalent-governance and A2A baselines, authorization timing, and a workload with repeated use and version changes across multiple agents.

## Files

- `benchmarks/integrated_v011/compare.py`: runnable integrated benchmark.
- `benchmarks/integrated_v011/wire_meter.py`: private-data-free counting hooks.
- `benchmarks/integrated_v011/worker_entry.py`: opt-in worker bootstrap without editing worker source.
- `benchmarks/integrated_v011/test_integrated_wire_v011.py`: 2 isolated black-box benchmark tests.
