# RC1 Evidence Summary — distinguish measured outcomes from unproven claims

Historical (research) results from the CAAIF development sessions. Source benchmarks under `benchmarks/` are included where available. These are **not** independent third-party results and not a fair A2A comparison.

| Experiment | Evidence | Limitation |
|---|---|---|
| Core/Three-Agent/Guarded SDK regression | 161 SDK tests passed in assembled v0.13 code; independently rerun with this candidate | Test scenarios synthetic; not a production security review |
| Cross-framework demo | LangGraph Reasoning and Microsoft Agent Framework task adapters exercised with deterministic content | No LLM reasoning quality benchmark |
| Context v0.8 large reused scenario | Selected inline 28,070 B; delta 17,677 B (37.0% reduction) | Mock policy/localhost; excludes WAN, real tokens |
| Integrated v0.11 large | ~83,725 measured B; 20 HTTP requests/scenario | Includes publication overhead; excludes response headers, TLS, WAN |
| Integrated v0.11 small | ~11,717 measured B; 20 HTTP requests/scenario | Publication dominates large synthetic contexts |
| v0.13 guarded demo | Rejected malicious proposal, altered action and replay; accepted legitimate summarization | Deterministic simulated injection, static credentials, local proof |

Primary next research metrics: unauthorized side-effect success, unnecessary recipient data exposure, task correctness, false-denial rate, model token usage and p95 latency. Pre-register hypotheses and compare with equivalent-control A2A agents; do not claim lower cost, security superiority or production-readiness without those studies.
