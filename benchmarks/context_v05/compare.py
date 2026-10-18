"""CAAIF v0.5 benchmark: full inline handoffs versus selected context references.

Real loopback HTTP exchanges through the existing ContextRelay, HTTPTransport,
AgentHTTPServer and LocalController. The remote agent is in another HTTP server
thread in this process, not a separate operating-system process. No LLMs.
Both alternatives use identical contracts, controller checks, and handler.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import secrets
import statistics
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caaif_core import LocalController, Denied
from caaif_core import http_transport as http

PROFILE_DIR = ROOT / 'examples' / 'three-agent'
PROFILE = json.loads((PROFILE_DIR / 'profile.json').read_text())
CONTRACTS = [json.loads(p.read_text()) for p in sorted((PROFILE_DIR / 'contracts').glob('*.json'))]
CONTRACT_ID = 'demo.three-agent.intent.v1'
IDS = {'conversational': 'demo.agent.conversational', 'reasoning': 'demo.agent.reasoning', 'task': 'demo.agent.task'}


class Measurements:
    def __init__(self):
        self.rows = []
        self._lock = threading.Lock()

    @contextmanager
    def capture(self):
        previous = http._send

        def instrumented(url, body, token, *, timeout=5.0):
            # Only sizes and durations: no payloads, credentials, or context values.
            start = time.perf_counter()
            data = previous(url, body, token, timeout=timeout)
            duration = 1000 * (time.perf_counter() - start)
            with self._lock:
                self.rows.append((len(http._json(body)), len(http._json(data)), duration))
            return data

        http._send = instrumented
        try:
            yield
        finally:
            http._send = previous

    def summary(self):
        return {'rpc': len(self.rows),
                'upload': sum(r[0] for r in self.rows),
                'download': sum(r[1] for r in self.rows),
                'bytes': sum(r[0] + r[1] for r in self.rows)}


def controller_and_agents(worker, relay, url, token):
    contracts = copy.deepcopy(CONTRACTS)
    for c in contracts:
        if c['contract_id'] == CONTRACT_ID:
            # Same contract for both modes. Increase limits only for synthetic
            # document test; do not alter the shipped contract or the SDK.
            c['limits']['max_request_bytes'] = 60000
            c['context_policy']['max_inline_bytes'] = 50000
    controller = LocalController(profile=copy.deepcopy(PROFILE), contracts=contracts,
                                 policy=lambda req, c: req['correlation_id'].startswith('bench-'),
                                 effect_policy=lambda req, c: req['input'].get('operation') == 'create_outline')
    handles = {}
    for role, agent_id in IDS.items():
        if role == 'reasoning':
            fn = http.HTTPTransport(url=url, recipient_id=agent_id, auth_token=token, relay=relay)
        else:
            fn = lambda req, ctx: {}
        handles[role] = controller.attach(agent_id, fn)
    return controller, handles


def agent_handler(request, context):
    if request['context_refs']:
        selected = context.resolve(request['context_refs'][0]['ref'])
        needed = selected['needed']
    else:
        needed = request['input']['document']['needed']
    return {'digest': hashlib.sha256(needed.encode('utf-8')).hexdigest()}


def payload(case: str):
    # Fixed-size printable inputs ensure deterministic, repeatable JSON lengths.
    if case == 'tiny':
        return {'needed': 'relevant 20-byte fact', 'irrelevant': 'x' * 30}
    if case == 'medium':
        return {'needed': 'Summary of selected text. ' * 5, 'irrelevant': 'x' * 2200}
    if case == 'large':
        return {'needed': 'Summary of selected text. ' * 5, 'irrelevant': 'x' * 18000}
    raise ValueError('unknown_case')


def measure_mode(mode, case, *, repeat, runs, warmup, worker_url, worker_token, relay):
    document = payload(case)
    expected_digest = hashlib.sha256(document['needed'].encode()).hexdigest()
    sizes, latencies, rpc_counts, responses = [], [], [], []
    for idx in range(warmup + runs):
        core, actors = controller_and_agents(agent_handler, relay, worker_url, worker_token)
        sender, recipient = actors['conversational'], actors['reasoning']
        correlation = f'bench-{mode}-{case}-{idx}'
        refs = []
        if mode == 'reference':
            # Registration/ingestion is done once, outside measured network
            # traffic. Only required context is published; no automatic selector.
            refs = [core.put_context(sender, ref=f'ctx:bench/{case}/{idx}', version='v1',
                                     scope='session.intent', value={'needed': document['needed']},
                                     readers={recipient.agent_id}, correlation_id=correlation)]
        metrics = Measurements()
        with metrics.capture():
            start = time.perf_counter()
            for j in range(repeat):
                request = core.new_request(sender, contract_id=CONTRACT_ID,
                    correlation_id=correlation, context_refs=refs,
                    data={'task': 'extract'} if mode == 'reference'
                    else {'task': 'extract', 'document': document})
                result = core.dispatch(sender, request)
                assert result['status'] == 'completed'
                assert result['output']['digest'] == expected_digest, 'non_equivalent_result'
            elapsed = (time.perf_counter() - start) * 1000
        if idx >= warmup:
            stat = metrics.summary()
            assert stat['rpc'] == repeat * (2 if mode == 'reference' else 1), 'unexpected_http_calls'
            sizes.append(stat['bytes'])
            rpc_counts.append(stat['rpc'])
            latencies.append(elapsed)
            responses.append(expected_digest)
    assert len(set(responses)) == 1
    return {'case': case, 'mode': mode, 'runs': runs, 'handoffs': repeat,
            'bytes': statistics.mean(sizes), 'rpc': statistics.mean(rpc_counts),
            'avg_ms': statistics.mean(latencies),
            'p95_ms': sorted(latencies)[max(0, (95 * len(latencies) + 99) // 100 - 1)]}


def run(runs=10, repeat=3, warmup=2, cases=('tiny', 'medium', 'large'), printer=print):
    if not (1 <= runs <= 10000 and 1 <= repeat <= 50 and 0 <= warmup <= 100):
        raise ValueError('invalid_benchmark_parameters')
    secret = secrets.token_urlsafe(32)
    all_results = []
    with http.ContextRelay() as relay, http.AgentHTTPServer(
        agent_id=IDS['reasoning'], auth_token=secret, handler=agent_handler) as worker:
        for case in cases:
            a = measure_mode('inline', case, repeat=repeat, runs=runs, warmup=warmup,
                             worker_url=worker.url, worker_token=secret, relay=relay)
            b = measure_mode('reference', case, repeat=repeat, runs=runs, warmup=warmup,
                             worker_url=worker.url, worker_token=secret, relay=relay)
            all_results.extend((a, b))
            delta = 100 * (a['bytes'] - b['bytes']) / a['bytes']
            printer(f'{case:6} | full={a["bytes"]:.0f} B / {a["rpc"]:.0f} HTTP / {a["avg_ms"]:.2f} ms'
                    f' | refs={b["bytes"]:.0f} B / {b["rpc"]:.0f} HTTP / {b["avg_ms"]:.2f} ms'
                    f' | wire savings={delta:+.1f}%')
    return all_results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--repeat', type=int, default=3, help='Handoffs sharing the same context per case')
    parser.add_argument('--warmup', type=int, default=2)
    parser.add_argument('--out', type=Path, help='Optional JSON summary path')
    args = parser.parse_args()
    print(f'CAAIF SDK v0.5 Context Benchmark | runs={args.runs} repeat={args.repeat} warmup={args.warmup}')
    print('Same Three-Agent profile contracts/policy; actual loopback HTTP for worker and context retrieval')
    results = run(args.runs, args.repeat, args.warmup)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({'results': results, 'note': 'HTTP application body sizes only; excludes context registration, headers and TLS; no LLM tokens.'}, indent=2))
        print('Results saved to:', args.out)
    print('Limitations: deterministic handler, local threads, controller pre-ingestion unmetered; no model tokens or real A2A baseline.')


if __name__ == '__main__':
    main()
