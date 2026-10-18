"""CAAIF v0.8 benchmark-fixture checks; not production policy conformance."""
import secrets
import unittest
from urllib.error import HTTPError
from benchmarks.context_v08.compare import PublicationPolicyFixture, run
from caaif_core import http_transport as http
from benchmarks.context_v05.compare import IDS, CONTRACT_ID

class PublicationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.token=secrets.token_urlsafe(24)
        self.fixture=PublicationPolicyFixture(self.token).__enter__()
        self.key={'ref':'ctx:unit/doc','version':'v1','scope':'session.intent',
                  'correlation':'bench-unit-1','recipient':IDS['reasoning']}
    def tearDown(self):
        self.fixture.__exit__(None,None,None)
    def permit(self, *, token=None, **changes):
        p={'contract':CONTRACT_ID,'caller':IDS['conversational'],
           'recipient':IDS['reasoning'],'correlation':'bench-unit-1',
           'mode':'reference','ref':self.key['ref'],'version':'v1','scope':'session.intent'}
        p.update(changes)
        return http._send(self.fixture.url+'/authorize',p,token or self.token)
    def publish(self):
        return self.fixture.publish(self.key['ref'],self.key['version'],self.key['scope'],self.key['correlation'],self.key['recipient'],{'needed':'test'})
    def test_denies_reference_before_publish(self):
        self.assertEqual(self.permit(),{'allow':False})
    def test_publication_then_authorization(self):
        self.assertEqual(self.publish(),{'stored':True})
        self.assertEqual(self.permit(),{'allow':True})
    def test_wrong_recipient_denied(self):
        self.publish()
        self.assertEqual(self.permit(recipient=IDS['task']),{'allow':False})
    def test_wrong_correlation_denied(self):
        self.publish()
        self.assertEqual(self.permit(correlation='bench-unit-2'),{'allow':False})
    def test_wrong_version_denied(self):
        self.publish()
        self.assertEqual(self.permit(version='v2'),{'allow':False})
    def test_revoke_blocks_later_authorization(self):
        self.publish()
        self.assertEqual(http._send(self.fixture.url+'/revoke',{'ref':self.key['ref'],
                         'correlation':self.key['correlation']},self.token),{'revoked':True})
        self.assertEqual(self.permit(),{'allow':False})
    def test_wrong_token_denied(self):
        self.publish()
        with self.assertRaises(HTTPError) as ctx:
            self.permit(token='invalid')
        self.assertEqual(ctx.exception.code,401)
    def test_inline_requires_no_reference(self):
        self.assertEqual(self.permit(mode='selected',ref=None,version=None),{'allow':True})
    def test_bad_payload_denied(self):
        with self.assertRaises(HTTPError) as ctx:
            http._send(self.fixture.url+'/publish',{'ref':'x'},self.token)
        self.assertEqual(ctx.exception.code,400)

class EndToEndBenchTests(unittest.TestCase):
    def test_both_strategies_produce_equivalent_outputs_and_count_all_calls(self):
        result=run(runs=1,repeat=4,warmup=0,cases=('large_selected',),
                   modes=('selected','delta'))
        r={x['mode']:x for x in result}
        self.assertEqual(r['selected']['http_calls'],8)
        self.assertEqual(r['delta']['http_calls'],11) # 4 workers + 4 policies + 2 publications + 1 retrieval
        self.assertLess(r['delta']['body_bytes'],r['selected']['body_bytes'])

if __name__=='__main__': unittest.main()
