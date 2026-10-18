import unittest
from caaif_core.adaptive_context import (AdaptiveContextPolicy, ContextMode,
                                         ContextPolicyDenied)


def sample(case):
    if case == 'tiny':
        return {'needed': 'relevant 20-byte fact', 'irrelevant': 'x' * 30}
    if case == 'medium':
        return {'needed': 'Summary of selected text. ' * 5, 'irrelevant': 'x' * 2200}
    if case == 'large':
        return {'needed': 'Summary of selected text. ' * 5, 'irrelevant': 'x' * 18000}
    raise ValueError(case)


class AdaptiveContextTests(unittest.TestCase):
    def setUp(self):
        self.p = AdaptiveContextPolicy(max_inline_bytes=1024, min_selection_savings=64)

    def choose(self, case, **kwargs):
        full = sample(case)
        return self.p.choose(full, {'needed': full['needed']}, **kwargs)

    def test_tiny_authorized_full_inline(self):
        self.assertEqual(self.choose('tiny', full_authorized=True).mode, ContextMode.INLINE_FULL)

    def test_medium_selective_inline(self):
        self.assertEqual(self.choose('medium', full_authorized=True).mode, ContextMode.INLINE_SELECTED)

    def test_large_selective_inline(self):
        self.assertEqual(self.choose('large', full_authorized=True).mode, ContextMode.INLINE_SELECTED)

    def test_default_never_sends_extra_context(self):
        self.assertEqual(self.choose('tiny').mode, ContextMode.INLINE_SELECTED)

    def test_reference_required(self):
        self.assertEqual(self.choose('tiny', reference_required=True).mode, ContextMode.REFERENCE_SELECTED)

    def test_reference_required_is_fail_closed(self):
        with self.assertRaises(ContextPolicyDenied):
            self.choose('tiny', reference_required=True, reference_available=False)

    def test_selected_too_large_uses_ref(self):
        self.assertEqual(self.p.choose({'x': 'a'*5000}, {'x': 'a'*3000}).mode, ContextMode.REFERENCE_SELECTED)

    def test_full_not_authorized_must_not_fall_back(self):
        with self.assertRaises(ContextPolicyDenied):
            self.p.choose({'x': 'a'*5000}, {'x': 'b'*3000}, reference_available=False)

    def test_reference_unavailable_inline_safe(self):
        self.assertEqual(self.choose('medium', reference_available=False).mode, ContextMode.INLINE_SELECTED)

    def test_validation(self):
        with self.assertRaises(ValueError):
            AdaptiveContextPolicy(max_inline_bytes=0)
        with self.assertRaises(ValueError):
            AdaptiveContextPolicy(min_selection_savings=-1)

    def test_multibyte_counts_utf8(self):
        d = self.p.choose({'x': '🌍' * 1000}, {'x': '🌍'})
        self.assertGreater(d.full_bytes, 4000)
        self.assertEqual(d.mode, ContextMode.INLINE_SELECTED)

    def test_no_bypass_of_inline_prohibition(self):
        d = self.p.choose({'x':'safe'}, {'x':'safe'}, selected_inline_authorized=False)
        self.assertEqual(d.mode, ContextMode.REFERENCE_SELECTED)


if __name__ == '__main__':
    unittest.main()
