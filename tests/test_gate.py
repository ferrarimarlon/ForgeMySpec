from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from support import copy_example_bundle

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
