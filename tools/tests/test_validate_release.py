"""Unit tests for release-validator reporting and safety gates."""
import tempfile
import unittest
from pathlib import Path
from tools.validate_release import check_benchmark, check_releasability, check_sources, write_markdown

class ValidatorTests(unittest.TestCase):
    def test_source_inventory_reports_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(check_sources(Path(d)))

    def test_release_review_marks_missing_license_and_packaging(self):
        with tempfile.TemporaryDirectory() as d:
            ids={x['code'] for x in check_releasability(Path(d))}
            self.assertIn('LICENSE_NOT_SELECTED',ids)
            self.assertIn('DISTRIBUTION_NOT_PACKAGED',ids)
            self.assertIn('NO_A2A_COMPARATOR',ids)

    def test_benchmark_rejects_absent_cases(self):
        self.assertIn('benchmark_results_missing_small_or_large',check_benchmark({'results':[]}))

    def test_benchmark_accepts_expected_stages(self):
        stage={name:{'calls':n} for name,n in {'publication':4,'provider_read_and_auth':8,'worker_dispatch':4,'callback_retrieval':4}.items()}
        def item(case):return {'case':case,'revocation_tested':True,'http_requests':20,'p50_ms':1,'p95_ms':2,'measured_combined_bytes':500,'operation_profile':stage}
        self.assertEqual(check_benchmark({'results':[item('small'),item('large')]}),[])

    def test_markdown_not_approved_even_when_tests_pass(self):
        doc=write_markdown({'timestamp_utc':'now','environment':{'python':'3.12','platform':'test'}, 'checks':[{'name':'demo','status':'PASS','required':True}], 'release_review':[{'code':'NO_A2A_COMPARATOR','message':'Not tested'}], 'benchmark':None})
        self.assertIn('NOT APPROVED',doc)
        self.assertIn('NO_A2A_COMPARATOR',doc)

if __name__=='__main__':unittest.main()
