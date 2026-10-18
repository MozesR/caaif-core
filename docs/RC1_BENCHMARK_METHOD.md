# Benchmark methodology and reproducibility

Benchmarks under `benchmarks/context_v05..08` and `benchmarks/integrated_v011*` were developed for synthetic localhost research. Avoid treating per-workflow byte counts as real-model performance claims. Include initial context publication, authorization, tool execution, model token usage, server-side headers, TLS/network metadata, and confidence intervals when running end-to-end comparisons.

A fair comparator should use an A2A-compatible implementation **with equivalent policy, context projection and auditing**, not ungoverned direct HTTP. Primary outcome measures are unnecessary recipient disclosure and unauthorized effect rate, with task quality, token/cost and latency secondary. RQ1-RQ4 hypotheses in `spec/TRUST_ARCHITECTURE_DRAFT3.md` are *proposed*, not confirmed.
