from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from support import EXAMPLE_BUNDLE as EXAMPLE, copy_example_bundle

from forgemyspec.bundle import BundleLayout
from forgemyspec.contract_lock import write_lock
from forgemyspec.dafny_runner import find_dafny, version_at_least
from forgemyspec.gate import BLOCKED, FAIL, PASS, run_gate
from forgemyspec.spec_io import load_spec


HAVE_DAFNY = find_dafny() is not None


class GateFaultInjectionTests(unittest.TestCase):
    """The five faults from the spec's success criteria. None of them needs Dafny to be detected."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = copy_example_bundle(Path(self._tmp.name))
        self.layout = BundleLayout.at(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def edit(self, path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_fails_at(self, stage_name: str) -> None:
        report = run_gate(str(self.root))
        self.assertFalse(report.passed)
        self.assertEqual(report.stage(stage_name).status, FAIL, report.stage(stage_name))
        for name in ("verify", "test", "audit", "translate", "python-boundary-tests", "mutation"):
            self.assertEqual(report.stage(name).status, BLOCKED)

    def test_assume_in_impl_fails_dafny_lint(self) -> None:
        self.edit(self.layout.impl, "final := start;", "assume start >= 0;\n    final := start;")
        self.assert_fails_at("dafny-lint")

    def test_removed_obligation_tag_fails_dafny_lint(self) -> None:
        self.edit(self.layout.contract, "    // @obligation replay\n", "")
        self.assert_fails_at("dafny-lint")

    def test_contract_byte_changed_after_lock_fails_contract_lock(self) -> None:
        data = self.layout.contract.read_bytes()
        self.layout.contract.write_bytes(data.replace(b"amount > 0 ==>", b"amount >= 1 ==>", 1))
        self.assert_fails_at("contract-lock")

    def test_uncovered_must_include_fails_obligation_coverage(self) -> None:
        spec = load_spec(str(self.layout.spec))
        spec["metadata"]["scope_contract"]["must_include"].append("monthly statement export")
        self.layout.spec.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
        self.assert_fails_at("obligation-coverage")

    def test_missing_dafny_fails_toolchain(self) -> None:
        with patch.dict(os.environ, {"FORGEMYSPEC_DAFNY": str(self.root / "no-such-dafny")}):
            self.assert_fails_at("toolchain")

    def test_version_comparison(self) -> None:
        self.assertTrue(version_at_least("4.11.0", "4.0"))
        self.assertTrue(version_at_least("4.0", "4.0.0"))
        self.assertFalse(version_at_least("3.13.1", "4.0"))


@unittest.skipUnless(HAVE_DAFNY, "dafny is not installed; CI installs it and runs these")
class GateEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = copy_example_bundle(Path(self._tmp.name))
        self.layout = BundleLayout.at(self.root)
        # Lock provisório só nesta cópia temporária: o lock real do exemplo é do usuário.
        write_lock(self.layout, load_spec(str(self.layout.spec)))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_example_bundle_passes_every_stage(self) -> None:
        report = run_gate(str(self.root))
        self.assertTrue(report.passed, [(s.name, s.status, s.details) for s in report.stages])
        self.assertTrue((self.layout.generated / "core-py" / "BudgetImpl.py").exists())

    def test_wrong_implementation_fails_verify(self) -> None:
        text = self.layout.impl.read_text(encoding="utf-8")
        self.layout.impl.write_text(text.replace("} else if amount > balance {", "} else if amount >= balance {"), encoding="utf-8")
        report = run_gate(str(self.root))
        self.assertEqual(report.stage("verify").status, FAIL)
        self.assertEqual(report.stage("mutation").status, BLOCKED)

    def test_weak_contract_lets_mutants_survive(self) -> None:
        # Drop every check on the rejected count (contract clause, loop invariant, test expectations),
        # re-approve, and the mutants that corrupt the count must survive and fail the gate.
        self.edit_all(
            (self.layout.contract, "    ensures rejected == CountRejected(start, txs)\n", ""),
            (self.layout.impl, "      invariant rejected + CountRejected(final, txs[i..]) == CountRejected(start, txs)\n", ""),
            (self.layout.tests, "    expect rejected == 2;\n", ""),
            (self.layout.tests, "expect empty == 3 && none == 0;", "expect empty == 3;"),
        )
        write_lock(self.layout, load_spec(str(self.layout.spec)))

        report = run_gate(str(self.root))
        mutation = report.stage("mutation")
        self.assertEqual(mutation.status, FAIL, [(s.name, s.status, s.details) for s in report.stages])
        self.assertTrue(any(line.startswith("survived: impl.dfy:") for line in mutation.details))

    def edit_all(self, *edits) -> None:
        for path, old, new in edits:
            text = path.read_text(encoding="utf-8")
            self.assertIn(old, text)
            path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()


VERIFY_OUTPUT = """impl.dfy(16,2): Error: a postcondition could not be proved on this return path
contract.dfy(45,40): Related location: this is the postcondition that could not be proved
Dafny program verifier finished with 9 verified, 1 error
"""


class EvidenceTests(unittest.TestCase):
    def test_attribution(self) -> None:
        from forgemyspec.gate import _Evidence, _attribute_dafny_tests, _attribute_verify, _impl_method_at, _obligations_by_method

        layout = BundleLayout.at(EXAMPLE)
        spec = load_spec(str(layout.spec))
        line = next(i for i, l in enumerate(layout.contract.read_text().splitlines(), 1)
                    if "ensures 0 < amount <= balance ==> o == Applied(balance - amount)" in l)
        ev = _Evidence(spec)
        _attribute_verify(ev, VERIFY_OUTPUT.replace("contract.dfy(45,", f"contract.dfy({line},"), layout)
        self.assertEqual([f["stage"] for f in ev.data["withdraw_exact"]["fails"]], ["verify"])
        self.assertEqual(ev.data["deposit_exact"]["fails"], [])

        ev = _Evidence(spec)
        _attribute_dafny_tests(ev, "BudgetTests.OverdraftIsRejected: FAILED\nBudgetTests.ReplayAppliesInOrder: PASSED\n", layout)
        self.assertTrue(ev.data["overdraft_rejected"]["fails"])
        self.assertTrue(ev.data["never_negative"]["fails"])  # the same test carries both tags
        self.assertTrue(ev.data["replay"]["tests_ok"])

        impl = layout.impl.read_text(encoding="utf-8")
        withdraw_line = next(i for i, l in enumerate(impl.splitlines(), 1) if "amount > balance" in l)
        self.assertEqual(_impl_method_at(impl, withdraw_line), "ApplyWithdraw")
        by_method = _obligations_by_method(layout.contract.read_text(encoding="utf-8"))
        self.assertEqual(set(by_method["ApplyWithdraw"]), {"withdraw_exact", "overdraft_rejected", "non_positive_rejected", "never_negative"})


@unittest.skipUnless(HAVE_DAFNY, "dafny is not installed; CI installs it and runs these")
class PlantedErrorsTests(unittest.TestCase):
    def test_stage(self) -> None:
        import shutil

        from support import KERNEL_BUNDLE

        with tempfile.TemporaryDirectory() as tmp:
            root = copy_example_bundle(Path(tmp))
            layout = BundleLayout.at(root)
            write_lock(layout, load_spec(str(layout.spec)))
            report = run_gate(str(root), write_cache=False)
            self.assertEqual(report.stage("planted-errors").status, PASS, report.stage("planted-errors").details)
            self.assertEqual(report.strength["planted"], [4, 4])

            # A planted error rejected by an obligation other than its @target measures nothing and fails the stage.
            impl = layout.impl.read_text(encoding="utf-8")
            wrong = "// @target deposit_exact\n// Planted error: bug is in withdraw, not deposit.\n" + impl.replace(
                "} else if amount > balance {", "} else if amount >= balance {")
            (layout.planted / "mislabeled.dfy").write_text(wrong, encoding="utf-8")
            write_lock(layout, load_spec(str(layout.spec)))
            report = run_gate(str(root), write_cache=False)
            details = report.stage("planted-errors").details
            self.assertEqual(report.stage("planted-errors").status, FAIL, details)
            self.assertTrue(any("mislabeled.dfy" in d and "wrong reason" in d and "withdraw_exact" in d for d in details), details)

            # In the kernel each method's clauses are independent: removing the two that cover an
            # implementation in draft lets the planted error `impl_allowed_without_lock` through.
            kernel = Path(tmp) / "kernel"
            shutil.copytree(KERNEL_BUNDLE, kernel, ignore=shutil.ignore_patterns("generated", "__pycache__"))
            k = BundleLayout.at(kernel)
            contract = k.contract.read_text(encoding="utf-8")
            for clause in ("    ensures c == BundleImpl && phase == Draft && formal ==> d == Deny(RImplWithoutLock)\n",
                           "    ensures c == BundleImpl && phase == Draft && !formal ==> d == Deny(RNotApproved)\n"):
                self.assertIn(clause, contract)
                contract = contract.replace(clause, "")
            k.contract.write_text(contract, encoding="utf-8")
            tests = k.tests.read_text(encoding="utf-8")
            for snippet in ("    var d2 := DecideEdit(BundleImpl, true, Draft, false, false);\n    expect d2 == Deny(RImplWithoutLock);\n",
                            "    var d3 := DecideEdit(BundleImpl, false, Draft, false, false);\n    expect d3 == Deny(RNotApproved);\n"):
                self.assertIn(snippet, tests)
                tests = tests.replace(snippet, "")
            k.tests.write_text(tests, encoding="utf-8")
            write_lock(k, load_spec(str(k.spec)))
            report = run_gate(str(kernel), write_cache=False)
            stage = report.stage("planted-errors")
            self.assertEqual(stage.status, FAIL, [(s.name, s.status, s.details) for s in report.stages])
            self.assertTrue(any("impl_allowed_without_lock.dfy" in d and "survived" in d for d in stage.details), stage.details)
            self.assertEqual(report.evidence["impl_requires_lock"]["status"], "leaking")
