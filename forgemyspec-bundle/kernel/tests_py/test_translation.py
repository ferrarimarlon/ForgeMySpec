"""The kernel translated to Python behaves like the proven Dafny, including string conversion."""

from __future__ import annotations

import unittest

import _dafny
import KernelImpl as K


def seq(*items):
    return _dafny.SeqWithoutIsStrInference([_dafny.Seq(i) for i in items])


class TranslationTests(unittest.TestCase):
    def test_translated_classification(self) -> None:
        s, r = K.default__.ClassifyObligation(K.Kind_BoundaryObligation(), 0, 0, True, False)
        self.assertTrue(s.is_Fragile and r.is_ByBoundary)
        s, r = K.default__.ClassifyObligation(K.Kind_DafnyObligation(), 0, 0, True, False)
        self.assertTrue(s.is_Proven and r.is_ByProof)

    def test_translated_requirement_points_to_worst(self) -> None:
        coverage = _dafny.SeqWithoutIsStrInference([K.Status_Proven(), K.Status_Leaking()])
        s, r = K.default__.RequirementStatus(K.Phase_Locked(), K.GateState_Current(), coverage)
        self.assertTrue(s.is_Leaking and r.is_ByObligation)
        self.assertEqual(r.index, 1)

    def test_translated_decision(self) -> None:
        d = K.default__.DecideEdit(K.Category_BundleContract(), True, K.Phase_Locked(), False, True)
        self.assertTrue(d.is_Deny and d.reason.is_RContractLocked)

    def test_translated_coverage_with_unicode_strings(self) -> None:
        mh, mp = K.default__.Coverage(seq("h1", "h2"), seq("naïve café ✓ 日本"),
                                      _dafny.SeqWithoutIsStrInference([seq("h2")]), _dafny.SeqWithoutIsStrInference([seq()]))
        self.assertEqual(["".join(x) for x in mh], ["h1"])
        self.assertEqual(["".join(x) for x in mp], ["naïve café ✓ 日本"])


if __name__ == "__main__":
    unittest.main()
