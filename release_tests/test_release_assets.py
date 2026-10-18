import tempfile, unittest, tomllib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ReleaseAssets(unittest.TestCase):
    def test_pyproject_flat_package(self):
        doc=tomllib.loads((ROOT/'pyproject.toml').read_text())
        self.assertEqual(doc['project']['name'],'caaif-core')
        self.assertEqual(doc['project']['version'],'0.1.0rc1')
        self.assertEqual(doc['tool']['setuptools']['packages']['find']['include'],['caaif_core*'])
        self.assertNotIn('license',doc['project'])  # legal adoption pending
    def test_apache_full_text_staged_not_adopted(self):
        s=(ROOT/'LICENSE.Apache-2.0.PROPOSED').read_text()
        self.assertIn('Apache License',s)
        self.assertIn('END OF TERMS AND CONDITIONS',s)
        self.assertIn('APPENDIX:',s)
    def test_release_gate_fails_closed(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from release_gate import inspect
        self.assertTrue(any('signed-release-approvals-missing' in b for b in inspect(ROOT)))
    def test_documents_exist(self):
        for p in ['SECURITY.md','CONTRIBUTING.md','GOVERNANCE.md','RELEASE_CHECKLIST.md','docs/THREAT_MODEL.md','docs/LEGAL_AND_PROVENANCE.md','docs/PACKAGING.md','docs/RELEASE_DECISIONS.md']:
            with self.subTest(p=p): self.assertTrue((ROOT/p).is_file())

if __name__=='__main__': unittest.main()
