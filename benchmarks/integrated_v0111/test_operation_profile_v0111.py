"""Black-box smoke tests for additive operation profiler."""
import unittest
from benchmarks.integrated_v0111.compare import run


class OperationProfileTests(unittest.TestCase):
    def test_four_operation_categories_and_total_count(self):
        report = run(runs=1, warmup=0, irrelevant_bytes=0)
        expected = {'publication': 4, 'provider_read_and_auth': 8,
                    'worker_dispatch': 4, 'callback_retrieval': 4}
        for key, expected_calls in expected.items():
            data = report['operation_profile'][key]
            self.assertEqual(data['calls'], expected_calls)
            self.assertGreater(data['combined_bytes'], 0)
            self.assertGreater(data['latency_ms_per_call'], 0)
        self.assertEqual(report['http_requests'], 20)
        total = sum(x['combined_bytes'] for x in report['operation_profile'].values())
        self.assertAlmostEqual(total, report['measured_combined_bytes'], delta=2)
        self.assertTrue(report['revocation_tested'])

    def test_large_irrelevant_context_changes_publication_not_policy_reads(self):
        small = run(runs=1, warmup=0, irrelevant_bytes=0)
        large = run(runs=1, warmup=0, irrelevant_bytes=1000)
        p = 'operation_profile'
        self.assertGreater(large[p]['publication']['combined_bytes'],
                           small[p]['publication']['combined_bytes'] + 3900)
        self.assertEqual(large[p]['provider_read_and_auth']['calls'], 8)
        self.assertEqual(large[p]['worker_dispatch']['calls'], 4)
        self.assertEqual(large[p]['callback_retrieval']['calls'], 4)


if __name__ == '__main__':
    unittest.main()
