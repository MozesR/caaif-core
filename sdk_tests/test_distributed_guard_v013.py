"""CAAIF v0.13 conformance checks, including actual separate OS processes."""
from __future__ import annotations
import concurrent.futures
import secrets
import time
import unittest
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from caaif_core.distributed_guard_v013 import (
    RemoteDenied, check_permit, sign_permit, post, TYP, AUD)
from caaif_core.remote_provider_v09 import ProviderClientV09,ProviderError
from examples.sdk_guarded_distributed_v013_demo import StackV013, IDS


class TestSignedPermitV013(unittest.TestCase):
    def setUp(self):
        self.key=secrets.token_bytes(32)
        self.claims={'typ':TYP,'aud':AUD,'iat':int(time.time()),'exp':int(time.time())+30,'jti':'j-001'}
    def test_signed_permit_roundtrip(self):
        self.assertEqual(check_permit(sign_permit(self.claims,self.key),self.key),self.claims)
    def test_signature_tampering_fails(self):
        token=sign_permit(self.claims,self.key)
        tampered=('A' if token[0]!='A' else 'B')+token[1:]
        with self.assertRaisesRegex(ValueError,'invalid_permit_signature'):
            check_permit(tampered,self.key)
    def test_expired_permit_rejected(self):
        c={**self.claims,'iat':100,'exp':110}
        with self.assertRaisesRegex(ValueError,'permit_invalid_or_expired'):
            check_permit(sign_permit(c,self.key),self.key,now=120)
    def test_wrong_audience_rejected(self):
        c={**self.claims,'aud':'another-tool'}
        with self.assertRaisesRegex(ValueError,'permit_invalid_or_expired'):
            check_permit(sign_permit(c,self.key),self.key)


class TestDistributedGuardV013(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=StackV013().start()
    @classmethod
    def tearDownClass(cls):
        cls.s.stop()
    def prepare(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        proposal=self.s.reason_propose(intent)
        permit=self.s.authorize(proposal['proposal_id'])['permit']
        return ctx,intent,permit
    def test_01_separate_processes_and_healthy(self):
        s=self.s
        self.assertEqual(len(s.processes),6)
        self.assertEqual(len({p.pid for p in s.processes}),6)
        self.assertTrue(all(p.is_alive() for p in s.processes))
    def test_02_legitimate_action_completed(self):
        ctx,intent,permit=self.prepare()
        result=self.s.task_execute(permit,intent)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['result']['resource'],'doc:42')
    def test_03_poisoned_proposal_denied(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        malicious=self.s.reason_propose(intent,poisoned=True)
        with self.assertRaises(RemoteDenied) as e:self.s.authorize(malicious['proposal_id'])
        self.assertEqual((e.exception.status,e.exception.code),(403,'proposal_outside_trusted_intent'))
    def test_04_reasoning_cannot_issue_own_permit(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        proposal=self.s.reason_propose(intent)
        with self.assertRaises(RemoteDenied) as e:
            post(self.s.urls['controller'],'/trusted/authorize',
                 {'proposal_id':proposal['proposal_id']},self.s.tokens['reason'])
        self.assertEqual(e.exception.code,'role_not_permitted')
    def test_05_wrong_actor_cannot_propose(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        body={k:intent[k] for k in ('intent_id','context_refs','purpose','action','resource','parameters')}
        body['contract_id']='demo.three-agent.execute.v1'
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['controller'],'/proposals',body,self.s.tokens['host'])
        self.assertEqual(e.exception.status,403)
    def test_06_forged_caller_role_string_rejected(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        body={k:intent[k] for k in ('intent_id','context_refs','purpose','action','resource','parameters')}
        body.update(contract_id='demo.three-agent.execute.v1',issuer='demo.agent.reasoning')
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['controller'],'/proposals',body,self.s.tokens['reason'])
        self.assertEqual(e.exception.status,400)
    def test_07_tampered_action_parameters_blocked(self):
        _,intent,permit=self.prepare()
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent,tamper={'parameters':{'format':'secret-export'}})
        self.assertEqual(e.exception.code,'action_binding_mismatch')
    def test_08_replay_is_blocked(self):
        _,intent,permit=self.prepare()
        self.s.task_execute(permit,intent)
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent)
        self.assertEqual(e.exception.code,'replay_denied')
    def test_09_two_concurrent_replays_only_one_succeeds(self):
        _,intent,permit=self.prepare()
        def attempt(_):
            try:self.s.task_execute(permit,intent);return 'completed'
            except RemoteDenied as e:return e.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,range(2)))
        self.assertCountEqual(results,['completed','replay_denied'])
    def test_10_permit_revocation_blocks_tool(self):
        _,intent,permit=self.prepare()
        claims=check_permit(permit,self.s.tokens['sign_key'].encode())
        post(self.s.urls['controller'],'/trusted/revoke',{'permit_id':claims['jti']},self.s.tokens['host'])
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent)
        self.assertEqual(e.exception.status,403)
    def test_11_provider_revocation_blocks_tool(self):
        ctx,intent,permit=self.prepare()
        ProviderClientV09(self.s.urls['provider'],self.s.tokens['p_host']).revoke(ref=ctx['ref'],correlation_id=ctx['correlation_id'])
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent)
        self.assertEqual(e.exception.status,403)
    def test_12_version_change_blocks_stale_permit(self):
        ctx,intent,permit=self.prepare()
        prov=ProviderClientV09(self.s.urls['provider'],self.s.tokens['p_host'])
        prov.publish(ref=ctx['ref'],version='v2',scope=ctx['scope'],correlation_id=ctx['correlation_id'],
                     value={'content':'new content','private':'not allowed'},
                     grants={'guarded-controller':['content'],'caaif-tool-gateway':['content'],IDS['reasoning']:['content']})
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent)
        self.assertEqual(e.exception.status,403)
    def test_13_direct_tool_without_task_identity_denied(self):
        _,intent,permit=self.prepare()
        body={'permit':permit,'action_request':{k:intent[k] for k in ('action','resource','parameters','purpose','intent_id')}}
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['gateway'],'/execute',body,self.s.tokens['reason'])
        self.assertEqual(e.exception.status,401)
    def test_14_untrusted_worker_cannot_be_called_anonymously(self):
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['reasoning'],'/invoke',{'any':1},'not-a-token')
        self.assertEqual(e.exception.status,401)
    def test_15_context_field_projection_enforced_at_provider(self):
        ctx=self.s.pub_context()
        c=ProviderClientV09(self.s.urls['provider'],self.s.tokens['p_gate'])
        selected=c.read(**ctx)['value']
        self.assertEqual(set(selected),{'content'})
        self.assertNotIn('private',selected)
    def test_16_controller_introspection_not_open_to_agents(self):
        _,intent,permit=self.prepare()
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['controller'],'/introspect',{'permit':permit},self.s.tokens['reason'])
        self.assertEqual(e.exception.status,403)
    def test_17_reference_not_grant(self):
        ctx=self.s.pub_context()
        # Even knowing the full reference does not confer a provider credential.
        with self.assertRaises(ProviderError) as e:
            ProviderClientV09(self.s.urls['provider'],self.s.tokens['p_host']).read(**ctx)
        self.assertEqual(e.exception.status,403)
    def test_18_audit_contains_no_document_or_token(self):
        _,intent,permit=self.prepare()
        data=post(self.s.urls['controller'],'/trusted/events',{},self.s.tokens['host'])
        serialized=str(data)
        self.assertNotIn('attacker.example',serialized)
        self.assertNotIn(permit,serialized)
    def test_19_trusted_disclosure_enforced(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        allowed=post(self.s.urls['controller'],'/trusted/disclose',
                     {'context_refs':intent['context_refs'],'recipient':'user-interface',
                      'purpose':'user-summary','correlation_id':intent['correlation_id']},self.s.tokens['host'])
        self.assertEqual(allowed,{'authorized':True})
        with self.assertRaises(RemoteDenied) as e:
            post(self.s.urls['controller'],'/trusted/disclose',
                 {'context_refs':intent['context_refs'],'recipient':'external-mail',
                  'purpose':'user-summary','correlation_id':intent['correlation_id']},self.s.tokens['host'])
        self.assertEqual(e.exception.code,'disclosure_denied')
    def test_20_disclosure_after_context_revocation_denied(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        ProviderClientV09(self.s.urls['provider'],self.s.tokens['p_host']).revoke(ref=ctx['ref'],correlation_id=ctx['correlation_id'])
        with self.assertRaises(RemoteDenied) as e:
            post(self.s.urls['controller'],'/trusted/disclose',
                 {'context_refs':intent['context_refs'],'recipient':'user-interface',
                  'purpose':'user-summary','correlation_id':intent['correlation_id']},self.s.tokens['host'])
        self.assertEqual(e.exception.status,403)
    def test_21_provenance_policy_denies_even_host_registered_action(self):
        ctx=self.s.pub_context()
        body={'intent_id':'intent:forbidden:'+ctx['ref'],
              'correlation_id':ctx['correlation_id'],'action':'email.send',
              'resource':'external:attacker.example',
              'parameters':{'recipient':'attacker.example'},'purpose':'user-summary',
              'context_refs':[{'ref':ctx['ref'],'version':ctx['version'],'scope':ctx['scope']}]}
        post(self.s.urls['controller'],'/trusted/intent',body,self.s.tokens['host'])
        proposal=self.s.reason_propose(body)
        with self.assertRaises(RemoteDenied) as e:
            self.s.authorize(proposal['proposal_id'])
        self.assertEqual(e.exception.code,'provenance_policy_denied')
    def test_22_untrusted_context_cannot_expand_purpose(self):
        ctx=self.s.pub_context()
        body={'intent_id':'intent:wrong-purpose:'+ctx['ref'],
              'correlation_id':ctx['correlation_id'],'action':'document.summarize',
              'resource':'doc:42','parameters':{'format':'bullets'},'purpose':'mass-export',
              'context_refs':[{'ref':ctx['ref'],'version':ctx['version'],'scope':ctx['scope']}]}
        post(self.s.urls['controller'],'/trusted/intent',body,self.s.tokens['host'])
        proposal=self.s.reason_propose(body)
        with self.assertRaises(RemoteDenied) as e:
            self.s.authorize(proposal['proposal_id'])
        self.assertEqual(e.exception.code,'provenance_policy_denied')
    def test_23_worker_credentials_not_shared(self):
        # Verify process arguments are minimized (config regression).
        import inspect
        from examples.sdk_guarded_distributed_v013_demo import StackV013
        source=inspect.getsource(StackV013.start)
        self.assertIn("'reasoning':('worker_reasoning','reason','p_reason')",source)
        self.assertIn("'task':('worker_task','task')",source)

if __name__=='__main__':unittest.main()
