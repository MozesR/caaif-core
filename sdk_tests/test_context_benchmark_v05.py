"""Validation of equivalent outputs, HTTP accounting, and authorization integrity."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.context_v05.compare import run, controller_and_agents, agent_handler, IDS
from caaif_core import Denied
from caaif_core.http_transport import ContextRelay, AgentHTTPServer


class ContextBenchmarkTests(unittest.TestCase):
    def test_both_modes_and_actual_http(self):
        r = run(runs=1, repeat=2, warmup=0, cases=('tiny',), printer=lambda _: None)
        self.assertEqual([x['rpc'] for x in r], [2, 4])
        self.assertGreater(r[0]['bytes'], 0)
        self.assertGreater(r[1]['bytes'], 0)

    def test_large_context_reference_reduces_bytes(self):
        r = run(runs=1, repeat=2, warmup=0, cases=('large',), printer=lambda _: None)
        self.assertLess(r[1]['bytes'], r[0]['bytes'])

    def test_tiny_payload_can_be_more_expensive_by_reference(self):
        r = run(runs=1, repeat=1, warmup=0, cases=('tiny',), printer=lambda _: None)
        self.assertGreater(r[1]['bytes'], r[0]['bytes'])

    def test_context_reader_restriction(self):
        with ContextRelay() as relay, AgentHTTPServer(agent_id=IDS['reasoning'], auth_token='x'*32, handler=agent_handler) as worker:
            core, handles = controller_and_agents(agent_handler, relay, worker.url, 'x'*32)
            ref = core.put_context(handles['conversational'], ref='ctx:bench/restricted', version='v1',
                scope='session.intent', value={'needed': 'private'}, readers={handles['task'].agent_id},
                correlation_id='bench-restricted')
            request = core.new_request(handles['conversational'], contract_id='demo.three-agent.intent.v1',
                correlation_id='bench-restricted', context_refs=[ref], data={'task': 'extract'})
            with self.assertRaises(Denied) as caught:
                core.dispatch(handles['conversational'], request)
            self.assertEqual(caught.exception.code, 'context_reader_denied')

    def test_same_results_repeated_runs(self):
        rows = run(runs=2, repeat=2, warmup=0, cases=('medium',), printer=lambda _: None)
        self.assertEqual(rows[0]['runs'], 2)
        self.assertEqual(rows[1]['runs'], 2)

if __name__ == '__main__':
    unittest.main()
