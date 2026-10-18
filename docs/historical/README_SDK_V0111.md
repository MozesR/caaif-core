# CAAIF Core SDK v0.11.1 — Operation-Level Integrated Profiling

This is an **additive benchmark**. It does not modify `caaif_core/`, the existing v0.11 benchmark, or the existing demos and credentials.

## Run from the existing CAAIF Core project folder

```bash
unzip -n ~/Downloads/CAAIF_Core_SDK_v0.11.1_Operation_Profiler_Addon.zip -d .
.venv/bin/python -m benchmarks.integrated_v0111.compare --runs 20 --warmup 5 --large-bytes 18000 --out benchmarks/integrated_v0111/results.json
.venv/bin/python -m unittest discover -s benchmarks/integrated_v0111 -p 'test_operation_profile_v0111.py' -v
```

The new benchmark starts a Context Provider in its own process, three separate worker processes, and the trusted Controller/relay in the benchmark process, exactly as v0.11. It runs four authorized handoffs with a post-workflow revocation denial. The revocation probe is excluded from successful-workflow byte counts and latencies.

The per-operation report includes request byte totals (including client HTTP request headers), response **body** bytes, request counts, and average client-side elapsed time per HTTP call. The measured stages are:

- **publication** (`/publish`): author publishes full context to the independent provider, including any deliberately irrelevant fields.
- **provider_read_and_auth** (`/read`): provider selects granted fields and runs its own retrieval-time policy. This stage includes policy evaluation but **cannot separate policy compute time** from service/network time.
- **worker_dispatch** (`/invoke`): Controller sends a controlled request to a worker agent.
- **callback_retrieval** (`/context/resolve`): worker retrieves its short-lived context view from the relay.

Neither the operation meter nor its JSON output records URLs, paths, headers, bearer credentials, document contents, or raw context; only a fixed stage label, role, byte count and event kind are written. The temporary raw metrics file is removed after the run.

**Interpretation and limits:** Per-stage HTTP elapsed times overlap with the total end-to-end workflow and should not be added naively; synchronous nested calls can cause double counting. The test does *not* measure policy compute time independently, actual LLM tokens, response headers, TLS/TCP, WAN latency, A2A protocol overhead, or an equivalent-control baseline. All results concern deterministic localhost fixtures and are **not** evidence of general A2A superiority.

A large synthetic private field is included to reveal the cost of unfiltered context **publication**. This alone is not proof that reference sharing is better than selective inline transfer; the next fair test should compare them with identical publication, security, and authorization requirements.
