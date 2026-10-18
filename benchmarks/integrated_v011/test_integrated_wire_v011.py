"""Black-box integration smoke test: actual separate Context Provider and worker processes."""
import unittest
from benchmarks.integrated_v011.compare import run


class IntegratedWireTests(unittest.TestCase):
    def test_successful_4_handoff_process_chain_and_revocation(self):
        r = run(runs=1, warmup=0, irrelevant_bytes=0)
        self.assertEqual(r['http_requests'], 20)
        self.assertGreater(r['request_wire_bytes'], 0)
        self.assertGreater(r['response_body_bytes'], 0)
        self.assertTrue(r['revocation_tested'])

    def test_publication_cost_is_counted(self):
        small = run(runs=1, warmup=0, irrelevant_bytes=0)
        large = run(runs=1, warmup=0, irrelevant_bytes=1000)
        self.assertEqual(small['http_requests'], large['http_requests'])
        self.assertGreater(large['request_wire_bytes'], small['request_wire_bytes'] + 3900)


if __name__ == '__main__':
    unittest.main()
