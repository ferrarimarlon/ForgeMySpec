from __future__ import annotations

import unittest

from support import EXAMPLE_BUNDLE

from forgemyspec.mutation import MutationReport, Mutant, generate_mutants, KILLED_TEST, INVALID, SURVIVED, _spread


SOURCE = """include "contract.dfy"
module Impl refines Spec {
  method M(a: int, s: seq<int>) returns (r: int)
  {
    // r := a + 1 in a comment stays untouched
    var t: seq<int> := s;
    r := a + 1; // @equivalent-mutant: demo reason
    while r < 10
      invariant r <= 10
    {
      r := r * 2;
      assert r > 0 || r <= 0;
    }
    r := -r;
  }
}
"""


class MutationGenerationTests(unittest.TestCase):
    def test_mutants_touch_only_behavioral_code_in_bodies(self) -> None:
        mutants, suppressed, candidates = generate_mutants(SOURCE, max_mutants=100)
        described = {(m.line, m.original, m.replacement) for m in mutants}
        self.assertIn((8, "<", "<="), described)
        self.assertIn((8, "10", "11"), described)
        self.assertIn((11, "*", "+"), described)
        self.assertIn((11, "2", "3"), described)
        lines = {m.line for m in mutants}
        self.assertNotIn(3, lines)   # signature
        self.assertNotIn(5, lines)   # comment
        self.assertNotIn(6, lines)   # generic type argument
        self.assertNotIn(9, lines)   # loop invariant
        self.assertNotIn(12, lines)  # assert
        self.assertNotIn(14, lines)  # unary minus
        self.assertEqual(suppressed, [(7, "demo reason")])
        self.assertEqual(candidates, len(mutants))

    def test_each_mutant_changes_exactly_one_token(self) -> None:
        mutants, _, _ = generate_mutants(SOURCE, max_mutants=100)
        for mutant in mutants:
            original_line = SOURCE.splitlines()[mutant.line - 1]
            mutated_line = mutant.source.splitlines()[mutant.line - 1]
            self.assertNotEqual(original_line, mutated_line)
            self.assertEqual(SOURCE.splitlines()[: mutant.line - 1], mutant.source.splitlines()[: mutant.line - 1])

    def test_cap_spreads_deterministically(self) -> None:
        mutants, _, candidates = generate_mutants((EXAMPLE_BUNDLE / "impl.dfy").read_text(), max_mutants=5)
        again, _, _ = generate_mutants((EXAMPLE_BUNDLE / "impl.dfy").read_text(), max_mutants=5)
        self.assertGreater(candidates, 5)
        self.assertEqual(len(mutants), 5)
        self.assertEqual([(m.line, m.column) for m in mutants], [(m.line, m.column) for m in again])
        self.assertEqual(_spread(list(range(10)), 3), [0, 4, 9])

    def test_kill_rate_ignores_invalid_mutants(self) -> None:
        report = MutationReport(
            mutants=[
                Mutant(1, 1, "<", "<=", "", status=KILLED_TEST),
                Mutant(2, 1, "<", "<=", "", status=SURVIVED),
                Mutant(3, 1, "<", "<=", "", status=INVALID),
            ]
        )
        self.assertEqual(report.scored, 2)
        self.assertEqual(report.kill_rate, 0.5)
        self.assertEqual(len(report.survivors), 1)


if __name__ == "__main__":
    unittest.main()
