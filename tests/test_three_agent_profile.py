"""Static role/contract fixture checks; NOT runtime conformance certification."""
import copy, json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.profile_rules import check_request, validate_manifest

def get(name):
    return json.loads((ROOT/'examples'/'three-agent'/name).read_text())

class ThreeAgentProfileFixtureTests(unittest.TestCase):
    def setUp(self):
        self.p=get('profile.json')
        self.rec=get('trusted_decision_record.json')
        self.decisions={self.rec['decision_ref']:self.rec}

    def edge(self,a,b):
        return get(f'contracts/{a}_to_{b}.json'), get(f'requests/{a}_to_{b}.json')

    def permit(self,a,b,**kwargs):
        c,r=self.edge(a,b)
        return check_request(self.p,c,r,r['caller_id'],trusted_decisions=self.decisions,**kwargs)

    def test_manifest_valid(self): self.assertTrue(validate_manifest(self.p))
    def test_all_four_edges_allowed(self):
        for a,b in [('conversational','reasoning'),('reasoning','task'),('task','reasoning'),('reasoning','conversational')]:
            with self.subTest(edge=f'{a}->{b}'):
                self.assertTrue(self.permit(a,b))
    def test_cross_role_identity_duplicate_rejected(self):
        p=copy.deepcopy(self.p);p['roles']['task']=[p['roles']['reasoning'][0]]
        with self.assertRaises(AssertionError):validate_manifest(p)
    def test_conversational_to_task_not_approved(self):
        c,r=self.edge('reasoning','task');r['caller_id']=self.p['roles']['conversational'][0]
        self.assertFalse(check_request(self.p,c,r,r['caller_id'],trusted_decisions=self.decisions))
    def test_forged_caller_identity_rejected(self):
        c,r=self.edge('conversational','reasoning')
        self.assertFalse(check_request(self.p,c,r,'intruder'))
    def test_wrong_contract_version_rejected(self):
        c,r=self.edge('conversational','reasoning');r['contract_version']='999'
        self.assertFalse(check_request(self.p,c,r,r['caller_id']))
    def test_wrong_recipient_rejected(self):
        c,r=self.edge('conversational','reasoning');r['recipient_id']='impostor'
        self.assertFalse(check_request(self.p,c,r,r['caller_id']))
    def test_missing_reasoning_decision_rejected(self):
        c,r=self.edge('reasoning','task')
        self.assertFalse(check_request(self.p,c,r,r['caller_id']))
    def test_fake_decision_reference_rejected(self):
        c,r=self.edge('reasoning','task');r['decision_ref']='decision:fake'
        self.assertFalse(check_request(self.p,c,r,r['caller_id'],trusted_decisions=self.decisions))
    def test_wrong_correlation_rejected(self):
        c,r=self.edge('reasoning','task');r['correlation_id']='not-this-workflow'
        self.assertFalse(check_request(self.p,c,r,r['caller_id'],trusted_decisions=self.decisions))
    def test_unapproved_policy_rejected(self):
        self.assertFalse(self.permit('reasoning','task',independent_policy_allows=False))
    def test_wrong_context_scope_rejected(self):
        c,r=self.edge('reasoning','task');r['context_refs'][0]['scope']='private.full-transcript'
        self.assertFalse(check_request(self.p,c,r,r['caller_id'],trusted_decisions=self.decisions))
    def test_missing_effect_idempotency_key_rejected(self):
        c,r=self.edge('reasoning','task');del r['idempotency_key']
        self.assertFalse(check_request(self.p,c,r,r['caller_id'],trusted_decisions=self.decisions))
    def test_expired_trusted_decision_rejected(self):
        c,r=self.edge('reasoning','task');d=copy.deepcopy(self.rec);d['expires_at']='2020-01-01T00:00:00Z'
        self.assertFalse(check_request(self.p,c,r,r['caller_id'],trusted_decisions={d['decision_ref']:d}))
    def test_extra_direct_edge_is_invalid(self):
        p=copy.deepcopy(self.p);p['allowed_edges'].append({'from_role':'conversational','to_role':'task',
                                    'contract_id':'bypass','capability':'task.execute'})
        with self.assertRaises(AssertionError):validate_manifest(p)

if __name__=='__main__':unittest.main()
