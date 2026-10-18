"""CAAIF SDK v0.6 adaptive context benchmark.

Extends the v0.5 loopback benchmark with SELECTIVE INLINE as a fair baseline.
Context selection is a preauthorized synthetic fixture, not model selection.
Metrics exclude ingestion, TLS/HTTP headers, and LLM tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.context_v05 import compare as prior
from caaif_core import http_transport as http
from caaif_core.adaptive_context import AdaptiveContextPolicy, ContextMode


def measure(mode, case, runs, repeat, warmup, relay, url, token, policy):
    document = prior.payload(case)
    selected = {'needed': document['needed']}  # synthetic trusted selector
    expected = hashlib.sha256(document['needed'].encode('utf-8')).hexdigest()
    stat = []
    chosen = set()
    for i in range(runs + warmup):
        core, handles = prior.controller_and_agents(prior.agent_handler, relay, url, token)
        sender, recipient = handles['conversational'], handles['reasoning']
        correlation = f'bench-v06-{mode}-{case}-{i}'
        if mode == 'adaptive':
            choice = policy.choose(document, selected, full_authorized=True)
            actual = choice.mode
        elif mode == 'full':
            actual = ContextMode.INLINE_FULL
        elif mode == 'selected':
            actual = ContextMode.INLINE_SELECTED
        elif mode == 'reference':
            actual = ContextMode.REFERENCE_SELECTED
        else:
            raise ValueError('unknown_mode')
        chosen.add(actual.value)
        refs = []
        if actual == ContextMode.REFERENCE_SELECTED:
            # Same authorized reference path as v0.5. Registration is unmetered.
            refs = [core.put_context(sender, ref=f'ctx:v06/{case}/{i}', version='v1',
                                     scope='session.intent', value=selected,
                                     readers={recipient.agent_id}, correlation_id=correlation)]
        metrics = prior.Measurements()
        with metrics.capture():
            start = time.perf_counter()
            for j in range(repeat):
                if actual == ContextMode.REFERENCE_SELECTED:
                    data = {'task': 'extract'}
                else:
                    data = {'task': 'extract', 'document':
                            document if actual == ContextMode.INLINE_FULL else selected}
                req = core.new_request(sender, contract_id=prior.CONTRACT_ID,
                                       correlation_id=correlation, context_refs=refs, data=data)
                result = core.dispatch(sender, req)
                assert result['status'] == 'completed'
                assert result['output']['digest'] == expected, 'results_not_equivalent'
            elapsed_ms = (time.perf_counter() - start) * 1000
        if i >= warmup:
            summary = metrics.summary()
            assert summary['rpc'] == repeat * (2 if refs else 1)
            stat.append((summary['bytes'], summary['rpc'], elapsed_ms))
    return {'strategy': mode, 'choice': ','.join(sorted(chosen)),
            'bytes': statistics.mean(x[0] for x in stat),
            'http': statistics.mean(x[1] for x in stat),
            'latency_ms': statistics.mean(x[2] for x in stat)}


def run(runs=30, repeat=3, warmup=5):
    if not (1 <= runs <= 10000 and 1 <= repeat <= 50 and 0 <= warmup <= 100):
        raise ValueError('invalid_benchmark_parameters')
    policy = AdaptiveContextPolicy(max_inline_bytes=1024, min_selection_savings=64)
    token = secrets.token_urlsafe(32)
    output = []
    with http.ContextRelay() as relay, http.AgentHTTPServer(
            agent_id=prior.IDS['reasoning'], auth_token=token,
            handler=prior.agent_handler) as worker:
        for case in ('tiny', 'medium', 'large'):
            measurements = {}
            for mode in ('full', 'selected', 'reference', 'adaptive'):
                measurements[mode] = measure(mode, case, runs, repeat, warmup,
                                             relay, worker.url, token, policy)
            output.append({'case': case, 'results': measurements})
            def part(m):
                x=measurements[m]
                return f'{x["bytes"]:.0f} B/{x["http"]:.0f} HTTP/{x["latency_ms"]:.2f} ms'
            print(f'{case:6} | full={part("full")} | selected={part("selected")}'
                  f' | refs={part("reference")}')
            print(f'       adaptive={measurements["adaptive"]["choice"]} : {part("adaptive")}')
    print('Limitations: deterministic loopback, no headers/TLS, no initial ingestion, no LLM tokens, no A2A baseline.')
    print('Important: selective inline is a required comparison; do not attribute selection gains to references.')
    return output


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', type=int, default=30)
    ap.add_argument('--repeat', type=int, default=3)
    ap.add_argument('--warmup', type=int, default=5)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    print(f'CAAIF Core SDK v0.6 Adaptive Context Benchmark | runs={a.runs} repeat={a.repeat} warmup={a.warmup}')
    rows = run(a.runs, a.repeat, a.warmup)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps({'results':rows}, indent=2))
        print('Saved:',a.out)
