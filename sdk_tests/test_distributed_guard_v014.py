"""Distributed v0.14 negative tests in SIX independent research processes."""
from __future__ import annotations

import concurrent.futures
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from caaif_core.distributed_guard_v013 import RemoteDenied, post
from examples.sdk_guarded_distributed_v014_demo import StackV014


class DistributedBoundedIntentV014(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=StackV014().start()

    @classmethod
    def tearDownClass(cls):
        cls.s.stop()

    def prepare(self, *, approved=True):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        proposal=self.s.reason_propose(intent)
        if approved:self.s.confirm(proposal['proposal_id'],intent['parameters'])
        return ctx,intent,proposal['proposal_id']

    def permit(self):
        _,intent,proposal=self.prepare()
        return intent,self.s.authorize(proposal)['permit']

    def test_six_independent_processes(self):
        self.assertEqual(len(self.s.processes),6)
        self.assertEqual(len(set(x.pid for x in self.s.processes)),6)
        self.assertNotIn('sign_key',self.s.tokens)

    def test_confirmed_bounded_proposal_completes(self):
        intent,permit=self.permit()
        self.assertTrue(permit.startswith('caaif-v014/'))
        result=self.s.task_execute(permit,intent)
        self.assertEqual(result['result']['format'],'paragraphs')

    def test_missing_confirmation_denied(self):
        _,_,proposal=self.prepare(approved=False)
        with self.assertRaises(RemoteDenied) as e:self.s.authorize(proposal)
        self.assertEqual(e.exception.code,'exact_parameter_confirmation_required')

    def test_reasoning_agent_cannot_confirm(self):
        _,intent,proposal=self.prepare(approved=False)
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['controller'],'/trusted/confirm',
            {'proposal_id':proposal,'approved_parameters':intent['parameters'],
             'approval_reference':'fake-user-approval'},self.s.tokens['reason'])
        self.assertEqual(e.exception.code,'role_not_permitted')

    def test_exact_value_confirmation_mismatch_denied(self):
        _,intent,proposal=self.prepare(approved=False)
        with self.assertRaises(RemoteDenied) as e:self.s.confirm(proposal,{'format':'bullets'})
        self.assertEqual(e.exception.code,'confirmation_parameters_mismatch')

    def test_poisoned_context_cannot_create_new_effect(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        proposal=self.s.reason_propose(intent,poisoned=True)
        with self.assertRaises(RemoteDenied) as e:self.s.authorize(proposal['proposal_id'])
        self.assertEqual(e.exception.code,'proposal_outside_trusted_intent')

    def test_action_parameter_substitution_denied(self):
        intent,permit=self.permit()
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent,tamper={'parameters':{'format':'raw'}})
        self.assertEqual(e.exception.code,'controller_denied')

    def test_wrong_action_even_after_intent_confirmation_denied(self):
        intent,permit=self.permit()
        with self.assertRaises(RemoteDenied):self.s.task_execute(permit,intent,tamper={'action':'email.send'})

    def test_replay_denied(self):
        intent,permit=self.permit()
        self.s.task_execute(permit,intent)
        with self.assertRaises(RemoteDenied) as e:self.s.task_execute(permit,intent)
        self.assertEqual(e.exception.code,'replay_denied')

    def test_parallel_gateways_same_permit_one_success(self):
        intent,permit=self.permit()
        def call(_):
            try:return self.s.task_execute(permit,intent)['status']
            except RemoteDenied as ex:return ex.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(call,range(2)))
        self.assertEqual(results.count('completed'),1)
        self.assertEqual(len(results),2)

    def test_revocation_blocks_introspection(self):
        intent,permit=self.permit()
        # Introspection response not exposed to host. We obtain opaque->id via
        # a denied terminal result? Use revocation by proposal's minted ID from
        # host events is not available; existing endpoint accepts permit_id only.
        # This test checks provider-context revocation instead.
        from caaif_core.remote_provider_v09 import ProviderClientV09
        descriptor=intent['context_refs'][0]
        ProviderClientV09(self.s.urls['provider'],self.s.tokens['p_host']).revoke(
            ref=descriptor['ref'],correlation_id=intent['correlation_id'])
        with self.assertRaises(RemoteDenied):self.s.task_execute(permit,intent)

    def test_gateway_cannot_treat_arbitrary_string_as_grant(self):
        ctx=self.s.pub_context()
        intent=self.s.intent(ctx)
        with self.assertRaises(RemoteDenied):self.s.task_execute('caaif-v014/fake',intent)

    def test_introspection_requires_gateway_identity(self):
        intent,permit=self.permit()
        action={k:intent[k] for k in ('action','resource','parameters','purpose','intent_id')}
        with self.assertRaises(RemoteDenied) as e:post(self.s.urls['controller'],'/introspect',
            {'permit':permit,'action_request':action,'task_principal':'demo.agent.task'},
            self.s.tokens['reason'])
        self.assertEqual(e.exception.code,'role_not_permitted')


if __name__=='__main__':unittest.main()
