from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import copy_example_bundle

from forgemyspec.bundle import BundleLayout
from forgemyspec.dafny_lint import lint_bundle_dafny, outline, strip_comments_and_strings
from forgemyspec.spec_io import load_spec


class ScannerTests(unittest.TestCase):
    def test_strip_keeps_offsets_and_blanks_comments_and_strings(self) -> None:
        text = 'x := "assume" // assume\n/* outer /* nested */ assume */ y\nz := \'a\'; w\' := 1'
        stripped = strip_comments_and_strings(text)
        self.assertEqual(len(stripped), len(text))
        self.assertEqual(stripped.count("\n"), text.count("\n"))
        self.assertNotIn("assume", stripped)
        self.assertIn("y", stripped)
        self.assertIn("w'", stripped)

    def test_outline_distinguishes_bodies_from_set_displays_and_attributes(self) -> None:
        source = """abstract module X {
  datatype R = A | B(x: int) { predicate Big() { B? && x > 3 } }
  function F(x: int): set<int> { {x} }
  function Len(s: seq<int>): nat decreases |s| { |s| }
  function G(x: int): int
  method M(x: int) returns (r: int)
    ensures r in {1, 2}
    ensures forall k :: k in {3} ==> k > 0
  method {:test} T() { var q := {1}; }
  method N(x: int) returns (r: int) ensures x' == x { r := 1; }
}"""
        members = {m.name: m for m in outline(source).members}
        self.assertTrue(members["Big"].has_body)
        self.assertEqual(members["Big"].container, "R")
        self.assertTrue(members["F"].has_body)
        self.assertTrue(members["Len"].has_body)
        self.assertFalse(members["G"].has_body)
        self.assertFalse(members["M"].has_body)
        self.assertEqual(members["M"].ensures_count, 2)
        self.assertEqual(members["T"].attributes, ["test"])
        self.assertTrue(members["N"].has_body)
        module = outline(source).modules[0]
        self.assertTrue(module.abstract)
        self.assertEqual(module.name, "X")


class BundleLintTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = copy_example_bundle(Path(self._tmp.name))
        self.layout = BundleLayout.at(self.root)
        self.spec = load_spec(str(self.layout.spec))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def edit(self, path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def codes(self) -> list:
        return [issue.code for issue in lint_bundle_dafny(self.layout, self.spec)]

    def test_example_bundle_is_clean(self) -> None:
        self.assertEqual(self.codes(), [])

    def test_banned_constructs_are_reported_outside_comments(self) -> None:
        self.edit(self.layout.impl, "final := start;", "assume start > 0; final := start; // assume ok")
        self.edit(self.layout.impl, "rejected := 0;", "rejected := 0; expect final >= 0;")
        issues = lint_bundle_dafny(self.layout, self.spec)
        banned = [issue for issue in issues if issue.code == "LINT-DFY-001"]
        self.assertEqual(len(banned), 2)
        self.assertTrue(all(issue.location.startswith("impl.dfy:") for issue in banned))

    def test_expect_is_allowed_in_tests(self) -> None:
        self.assertNotIn("LINT-DFY-001", self.codes())

    def test_vacuous_contract_clauses_are_banned(self) -> None:
        self.edit(self.layout.contract, "requires balance >= 0\n    // @obligation deposit_exact", "requires false\n    // @obligation deposit_exact")
        self.assertIn("LINT-DFY-001", self.codes())

    def test_contract_function_without_body_is_reported(self) -> None:
        self.edit(
            self.layout.contract,
            "  function IsRejected(balance: int, tx: Tx): bool\n  {\n    match tx\n    case Deposit(a) => a <= 0\n    case Withdraw(a) => a <= 0 || a > balance\n  }\n",
            "  function IsRejected(balance: int, tx: Tx): bool\n",
        )
        self.assertIn("LINT-DFY-010", self.codes())

    def test_contract_method_with_body_or_without_ensures_is_reported(self) -> None:
        self.edit(
            self.layout.contract,
            "    ensures o.balance >= 0\n",
            "    ensures o.balance >= 0\n  {\n    o := Rejected(balance, Overdraft);\n  }\n",
        )
        self.edit(self.layout.contract, "    ensures final >= 0\n}", "    ensures final >= 0\n  method Extra(x: int) returns (y: int)\n}")
        codes = self.codes()
        self.assertIn("LINT-DFY-009", codes)
        self.assertIn("LINT-DFY-011", codes)

    def test_missing_obligation_tags_are_reported(self) -> None:
        self.edit(self.layout.contract, "    // @obligation overdraft_rejected\n", "")
        self.edit(self.layout.tests, "  // @obligation replay\n", "")
        codes = self.codes()
        self.assertIn("LINT-DFY-005", codes)
        self.assertIn("LINT-DFY-006", codes)

    def test_unknown_tag_and_wrong_module_shape_are_reported(self) -> None:
        self.edit(self.layout.tests, "// @obligation replay", "// @obligation replay, made_up")
        self.edit(self.layout.contract, "abstract module BudgetCore", "module BudgetCore")
        codes = self.codes()
        self.assertIn("LINT-DFY-007", codes)
        self.assertIn("LINT-DFY-003", codes)

    def test_missing_file_is_reported(self) -> None:
        self.layout.tests.unlink()
        self.assertEqual(self.codes(), ["LINT-DFY-000"])

    def test_lock_time_lint_does_not_need_impl(self) -> None:
        self.layout.impl.unlink()
        self.assertEqual(self.codes(), ["LINT-DFY-000"])
        self.assertEqual(lint_bundle_dafny(self.layout, self.spec, require_impl=False), [])


if __name__ == "__main__":
    unittest.main()
