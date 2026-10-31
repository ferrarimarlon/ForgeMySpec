from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import copy_example_bundle

from forgemyspec.bundle import BundleLayout
from forgemyspec.contract_lock import check_lock, write_lock
from forgemyspec.spec_io import load_spec


class ContractLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.layout = BundleLayout.at(copy_example_bundle(Path(self._tmp.name)))
        self.spec = load_spec(str(self.layout.spec))
        write_lock(self.layout, self.spec)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def messages(self, spec=None) -> list:
        return [issue.message for issue in check_lock(self.layout, spec or self.spec)]

    def test_fresh_lock_passes(self) -> None:
        self.assertEqual(self.messages(), [])

    def test_single_byte_change_in_contract_is_detected(self) -> None:
        data = bytearray(self.layout.contract.read_bytes())
        data[-2] = ord(" ") if data[-2] != ord(" ") else ord("\t")
        self.layout.contract.write_bytes(bytes(data))
        self.assertTrue(any("contract.dfy changed" in message for message in self.messages()))

    def test_tests_and_formal_changes_are_detected(self) -> None:
        self.layout.tests.write_text(self.layout.tests.read_text() + "\n", encoding="utf-8")
        self.spec["formal"]["obligations"][0]["statement"] += " (edited)"
        messages = self.messages()
        self.assertTrue(any("tests.dfy changed" in message for message in messages))
        self.assertTrue(any("formal section changed" in message for message in messages))

    def test_spec_version_bump_requires_relock(self) -> None:
        self.spec["version"] = "0.2"
        self.assertTrue(any("spec version changed" in message for message in self.messages()))

    def test_impl_changes_do_not_touch_the_lock(self) -> None:
        self.layout.impl.write_text(self.layout.impl.read_text() + "\n// refactor\n", encoding="utf-8")
        self.assertEqual(self.messages(), [])

    def test_missing_lock_fails(self) -> None:
        self.layout.lock.unlink()
        self.assertEqual([issue.code for issue in check_lock(self.layout, self.spec)], ["LOCK-001"])


if __name__ == "__main__":
    unittest.main()
