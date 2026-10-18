"""Loopback HTTP provider contract tests; no external dependencies."""
import secrets
import unittest
from caaif_core.remote_provider_v09 import ContextProviderV09, ProviderClientV09, ProviderError


class RemoteContextTests(unittest.TestCase):
    def setUp(self):
        self.tokens = {x: secrets.token_urlsafe(32) for x in ('conversation', 'reasoning', 'task', 'other')}
        self.allowed = {'reasoning', 'task'}
        self.provider = ContextProviderV09(
            self.tokens,
            authorize_read=lambda actor, ref, version, scope, correlation:
            actor in self.allowed and ref == 'ctx:test' and
            correlation == 'corr:1' and scope == 'session.intent'
        ).start()
        self.owner = ProviderClientV09(self.provider.url, self.tokens['conversation'])
        self.reason = ProviderClientV09(self.provider.url, self.tokens['reasoning'])
        self.task = ProviderClientV09(self.provider.url, self.tokens['task'])
        self.other = ProviderClientV09(self.provider.url, self.tokens['other'])
        self.descriptor = dict(ref='ctx:test', version='v1', scope='session.intent', correlation_id='corr:1')
        self.value = {'reasoning': 'plan', 'task': 'execute', 'private': 'hidden'}

    def tearDown(self):
        self.provider.close()

    def publish(self, *, version='v1', value=None, grants=None):
        self.owner.publish(ref='ctx:test', version=version, scope='session.intent', correlation_id='corr:1',
                           value=value if value is not None else self.value,
                           grants=grants if grants is not None else {'reasoning':['reasoning'], 'task':['task']})

    def denied(self, call, status=403, code=None):
        with self.assertRaises(ProviderError) as ctx:
            call()
        self.assertEqual(ctx.exception.status, status)
        if code:
            self.assertEqual(ctx.exception.code, code)

    def test_reader_receives_only_granted_fields(self):
        self.publish()
        self.assertEqual(self.reason.read(**self.descriptor)['value'], {'reasoning':'plan'})
        self.assertEqual(self.task.read(**self.descriptor)['value'], {'task':'execute'})

    def test_unauthorized_reader(self):
        self.publish()
        self.denied(lambda: self.other.read(**self.descriptor), code='context_reader_denied')

    def test_wrong_scope(self):
        self.publish()
        self.denied(lambda: self.reason.read(**dict(self.descriptor,scope='organization')))

    def test_wrong_correlation(self):
        self.publish()
        self.denied(lambda: self.reason.read(**dict(self.descriptor,correlation_id='corr:2')))

    def test_wrong_version(self):
        self.publish()
        self.denied(lambda: self.reason.read(**dict(self.descriptor,version='v2')))

    def test_provider_policy_revocation_rechecked(self):
        self.publish()
        self.reason.read(**self.descriptor)
        self.allowed.remove('reasoning')
        self.denied(lambda: self.reason.read(**self.descriptor), code='context_reader_denied')

    def test_owner_revocation(self):
        self.publish()
        self.owner.revoke(ref='ctx:test', correlation_id='corr:1')
        self.denied(lambda: self.reason.read(**self.descriptor), code='context_unavailable')

    def test_nonowner_cannot_revoke(self):
        self.publish()
        self.denied(lambda: self.task.revoke(ref='ctx:test', correlation_id='corr:1'), code='revoke_not_permitted')

    def test_updates_are_versioned(self):
        self.publish()
        self.publish(version='v2', value={'reasoning':'new plan', 'task':'new instruction'})
        self.denied(lambda: self.reason.read(**self.descriptor), code='context_version_conflict')
        self.assertEqual(self.reason.read(**dict(self.descriptor,version='v2'))['value'], {'reasoning':'new plan'})

    def test_duplicate_version_rejected(self):
        self.publish()
        self.denied(lambda: self.publish(), status=409, code='immutable_context_version')

    def test_invalid_token(self):
        # Token must be same length but different from any configured actor.
        fake = ProviderClientV09(self.provider.url, secrets.token_urlsafe(32))
        self.publish()
        self.denied(lambda: fake.read(**self.descriptor), status=401, code='unauthorized')

    def test_grants_do_not_override_provider_policy(self):
        self.publish(grants={'reasoning':['private'], 'other':['private']})
        self.denied(lambda: self.other.read(**self.descriptor), code='context_reader_denied')
        self.assertEqual(self.reason.read(**self.descriptor)['value'], {'private':'hidden'})

    def test_immutable_correlation_on_update(self):
        self.publish()
        self.denied(lambda: self.owner.publish(ref='ctx:test', version='v2',
                    scope='session.intent', correlation_id='corr:2', value=self.value,
                    grants={'reasoning':['reasoning']}), code='context_boundary_immutable')

    def test_ref_is_not_available_after_revoke_even_new_version(self):
        self.publish()
        self.owner.revoke(ref='ctx:test', correlation_id='corr:1')
        self.denied(lambda: self.publish(version='v2'), status=409, code='revoked_reference_cannot_update')

    def test_permission_failure_is_fail_closed(self):
        self.publish()
        self.provider._authorize_read = lambda *_: (_ for _ in ()).throw(RuntimeError('policy_down'))
        self.denied(lambda: self.reason.read(**self.descriptor), code='context_reader_denied')


if __name__ == '__main__':
    unittest.main()
