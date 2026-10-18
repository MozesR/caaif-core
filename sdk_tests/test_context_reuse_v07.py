import unittest
from caaif_core.context_reuse import VersionedContextCache, ContextCacheDenied, fingerprint, string_splice

class ContextReuseTests(unittest.TestCase):
    def setUp(self):
        self.allowed = {('reasoning', 'doc', 'v1', 'session.intent', 'run-a')}
        self.clock = [0]
        self.cache = VersionedContextCache(lambda *key: key in self.allowed,
                                           ttl_seconds=10, max_entries=2,
                                           clock=lambda: self.clock[0])
        self.k = ('reasoning', 'doc', 'v1', 'session.intent', 'run-a')

    def test_miss_then_hit(self):
        self.assertIsNone(self.cache.get(*self.k))
        self.cache.store(*self.k, {'needed': 'abc'})
        self.assertEqual(self.cache.get(*self.k), {'needed': 'abc'})
    def test_copy_no_mutation(self):
        self.cache.store(*self.k, {'needed': ['a']})
        got = self.cache.get(*self.k); got['needed'].append('evil')
        self.assertEqual(self.cache.get(*self.k), {'needed':['a']})
    def test_revocation_blocks_existing_cache(self):
        self.cache.store(*self.k, {'needed': 'abc'})
        self.allowed.clear()
        with self.assertRaises(ContextCacheDenied): self.cache.get(*self.k)
    def test_other_recipient_blocked(self):
        self.cache.store(*self.k, {'needed': 'abc'})
        with self.assertRaises(ContextCacheDenied): self.cache.get('task',*self.k[1:])
    def test_other_correlation_blocked(self):
        self.cache.store(*self.k, {'needed': 'abc'})
        with self.assertRaises(ContextCacheDenied): self.cache.get(*self.k[:-1], 'run-b')
    def test_expired_cache_misses(self):
        self.cache.store(*self.k, {'needed': 'abc'}); self.clock[0]=11
        self.assertIsNone(self.cache.get(*self.k))
    def test_patch_update_and_old_invalidation(self):
        self.cache.store(*self.k, {'needed': 'abcWORLDxyz'})
        newk = ('reasoning','doc','v2','session.intent','run-a'); self.allowed.add(newk)
        nxt={'needed':'abcHELLOxyz'}
        patch={'changes':{'needed':string_splice('abcWORLDxyz',nxt['needed'])},'digest':fingerprint(nxt)}
        self.assertEqual(self.cache.delta(*self.k[:2], 'v1','v2',*self.k[3:],patch),nxt)
        self.assertIsNone(self.cache.get(*self.k))
        self.assertEqual(self.cache.get(*newk), nxt)
    def test_digest_mismatch_rejected_atomically(self):
        self.cache.store(*self.k, {'needed':'before'})
        self.allowed.add(('reasoning','doc','v2','session.intent','run-a'))
        patch={'changes':{'needed':string_splice('before','after')},'digest':'0'*64}
        with self.assertRaises(ContextCacheDenied):
            self.cache.delta('reasoning','doc','v1','v2','session.intent','run-a',patch)
        self.assertEqual(self.cache.get(*self.k),{'needed':'before'})
    def test_cache_base_missing_denies(self):
        self.allowed.add(('reasoning','doc','v2','session.intent','run-a'))
        with self.assertRaises(ContextCacheDenied):
            self.cache.delta('reasoning','doc','v1','v2','session.intent','run-a',{'changes':{},'digest':'0'*64})
    def test_invalid_patch_rejected(self):
        self.cache.store(*self.k, {'needed':'abc'})
        self.allowed.add(('reasoning','doc','v2','session.intent','run-a'))
        with self.assertRaises(ContextCacheDenied):
            self.cache.delta('reasoning','doc','v1','v2','session.intent','run-a',{'changes':{'needed':{'prefix':30,'delete':0,'insert':'x'}},'digest':'0'*64})
    def test_max_value(self):
        cache=VersionedContextCache(lambda *x:True,max_value_bytes=10)
        with self.assertRaises(ContextCacheDenied):cache.store(*self.k, {'needed':'too many bytes'})
    def test_capacity_lru(self):
        self.cache.store(*self.k, {'needed':'abc'})
        for ver in ('v2','v3'):
            key=('reasoning','doc',ver,'session.intent','run-a'); self.allowed.add(key)
            self.cache.store(*key, {'needed':ver})
        self.assertIsNone(self.cache.get(*self.k))
    def test_invalidate(self):
        self.cache.store(*self.k, {'needed':'abc'})
        self.cache.invalidate(ref='doc')
        self.assertIsNone(self.cache.get(*self.k))
    def test_authorizer_failure_fails_closed(self):
        c=VersionedContextCache(lambda *a:1/0)
        with self.assertRaises(ContextCacheDenied):c.get(*self.k)
    def test_splice_empty_and_unicode(self):
        self.assertEqual(string_splice('ab猫cd', 'ab犬cd'),{'prefix':2,'delete':1,'insert':'犬'})
    def test_oversized_reference_does_not_bypass_policy(self):
        self.cache.store(*self.k, {'needed':'x'*100})
        self.allowed.clear()
        with self.assertRaises(ContextCacheDenied):self.cache.get(*self.k)

if __name__=='__main__':unittest.main()
