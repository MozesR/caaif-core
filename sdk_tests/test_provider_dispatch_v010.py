import json
import secrets
import unittest
from pathlib import Path

from caaif_core.local import Denied
from caaif_core.provider_dispatch_v010 import ProviderBackedController
from caaif_core.remote_provider_v09 import ContextProviderV09, ProviderClientV09, ProviderError

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / 'examples' / 'three-agent'
IDS = {'conversational': 'demo.agent.conversational', 'reasoning': 'demo.agent.reasoning', 'task': 'demo.agent.task'}


class ProviderDispatchTests(unittest.TestCase):
    def setUp(self):
        self.readers_allowed = True
        self.credentials = {aid: secrets.token_urlsafe(32) for aid in IDS.values()}
        def allow(actor, ref, version, scope, correlation):
            return self.readers_allowed and not ref.endswith('/blocked')
        self.provider = ContextProviderV09(self.credentials, authorize_read=allow).start()
        self.clients = {aid: ProviderClientV09(self.provider.url, key) for aid, key in self.credentials.items()}
        contracts = [json.loads(p.read_text()) for p in sorted((CFG/'contracts').glob('*.json'))]
        self.core = ProviderBackedController(provider_clients=self.clients, contracts=contracts,
             profile=json.loads((CFG/'profile.json').read_text()), policy=lambda r,c:True,
             effect_policy=lambda r,c:True)
        self.calls = {}
        for role, aid in IDS.items():
            def handler(req, ctx):
                return {'selection': ctx.resolve(req['context_refs'][0]['ref'])}
            self.calls[role] = self.core.attach(aid, handler)
        self.corr = 'integration-test-001'

    def tearDown(self):
        self.provider.close()

    def publish(self, *, ref='ctx:integration/001', version='v1', grants=None):
        conv = self.calls['conversational']
        return self.core.publish_remote(conv, ref=ref,version=version,
            scope='session.intent', correlation_id=self.corr,
            value={'topic': 'hello', 'private': 'not transmitted'},
            grants=grants or {self.calls['reasoning'].agent_id:['topic']})

    def dispatch(self, context):
        conv = self.calls['conversational']
        req = self.core.new_request(conv,contract_id='demo.three-agent.intent.v1',
             correlation_id=self.corr, context_refs=[context], data={'intent':'analyze'})
        return self.core.dispatch(conv,req)

    def test_remote_fields_not_locally_stored(self):
        c = self.publish()
        self.assertEqual(self.core._contexts[c['ref']]['value'], {})
        self.assertEqual(self.dispatch(c)['output']['selection'], {'topic':'hello'})
        self.assertNotIn('private', str(self.core.events))

    def test_provider_revocation_denies_existing_reference(self):
        c = self.publish()
        self.assertEqual(self.dispatch(c)['status'], 'completed')
        self.clients[self.calls['conversational'].agent_id].revoke(ref=c['ref'], correlation_id=self.corr)
        with self.assertRaisesRegex(Denied, 'provider_context_denied'):
            self.dispatch(c)

    def test_provider_policy_denies_regardless_of_local_grant(self):
        c = self.publish()
        self.readers_allowed = False
        with self.assertRaisesRegex(Denied, 'provider_context_denied'):
            self.dispatch(c)

    def test_provider_stale_version_rejected(self):
        c = self.publish(version='v1')
        current=self.publish(version='v2')
        with self.assertRaisesRegex(Denied, 'context_version_conflict'):
            self.dispatch(c)
        self.assertEqual(self.dispatch(current)['output']['selection'], {'topic':'hello'})

    def test_provider_policy_denial_on_initial_dispatch(self):
        c=self.publish(ref='ctx:integration/blocked')
        with self.assertRaisesRegex(Denied, 'provider_context_denied'):
            self.dispatch(c)

    def test_remote_publish_failure_restores_metadata(self):
        c=self.publish(ref='ctx:integration/x')
        # Provider revocation must block re-publication, and local version remains v1.
        self.clients[self.calls['conversational'].agent_id].revoke(ref=c['ref'], correlation_id=self.corr)
        with self.assertRaises(ProviderError):
            self.publish(ref=c['ref'],version='v2')
        self.assertEqual(self.core._contexts[c['ref']]['version'], 'v1')

    def test_context_is_not_exposed_to_non_reader(self):
        c=self.publish()
        with self.assertRaises(ProviderError):
            self.clients[self.calls['task'].agent_id].read(ref=c['ref'],version='v1',
                scope='session.intent', correlation_id=self.corr)

    def test_revocation_between_dispatch_preflight_and_retrieval(self):
        c = self.publish(ref='ctx:integration/midflight')
        owner_client = self.clients[self.calls['conversational'].agent_id]
        def handler(req, ctx):
            owner_client.revoke(ref=c['ref'],correlation_id=self.corr)
            return {'selection': ctx.resolve(c['ref'])}
        self.core._handlers[self.calls['reasoning'].agent_id] = handler
        with self.assertRaises(Denied):
            self.dispatch(c)
        self.assertEqual(sum(e['event']=='completed' for e in self.core.events),0)

    def test_interaction_policy_still_independent_from_provider(self):
        c = self.publish(ref='ctx:integration/policy')
        self.core._policy = lambda req, contract: False
        with self.assertRaisesRegex(Denied,'policy_denied'):
            self.dispatch(c)

    def test_two_remote_read_authorizations_per_retrieval(self):
        c=self.publish()
        client=self.clients[self.calls['reasoning'].agent_id]
        before=client.calls
        self.dispatch(c)
        self.assertEqual(client.calls-before,2)


if __name__=='__main__':
    unittest.main()
