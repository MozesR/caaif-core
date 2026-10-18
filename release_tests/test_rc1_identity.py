import unittest, tomllib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class RC1IdentityTests(unittest.TestCase):
    def test_rc1_version(self):
        data=tomllib.loads((ROOT/'pyproject.toml').read_text())
        self.assertEqual(data['project']['version'],'0.1.0rc1')
        self.assertNotIn('license',data['project'])
    def test_guarded_code_present(self):
        code=(ROOT/'caaif_core'/'guarded.py').read_text()
        self.assertIn('class GuardedLocalController',code)
        self.assertIn('legacy_decision_issuer_disabled',code)
    def test_dist_guard_present(self):
        self.assertTrue((ROOT/'caaif_core'/'distributed_guard_v013.py').is_file())
    def test_no_active_license(self):
        self.assertFalse((ROOT/'LICENSE').exists())
        self.assertTrue((ROOT/'LICENSE.Apache-2.0.PROPOSED').exists())
    def test_release_docs_present(self):
        for p in ['docs/RC1_SECURITY_ASSESSMENT.md','docs/RC1_RELEASE_STATUS.md', 'RELEASE_CHECKLIST.md']:
            with self.subTest(path=p):
                self.assertTrue((ROOT/p).is_file())
