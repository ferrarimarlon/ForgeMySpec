from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from shell import budget_cli


def run_cli(ledger_text: str, *extra: str):
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.txt"
        ledger.write_text(ledger_text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = budget_cli.main([str(ledger), *extra])
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_replays_ledger_through_verified_core(self) -> None:
        code, out, _ = run_cli("deposit 10\nwithdraw 4\n# comment\nwithdraw 7\ndeposit -1\n\ndeposit 2\n")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "balance=8 rejected=2")

    def test_malformed_line_reports_line_number(self) -> None:
        code, out, err = run_cli("deposit 10\nrefund 3\n")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("line 2", err)

    def test_non_integer_amount_reports_line_number(self) -> None:
        code, _, err = run_cli("deposit 10\nwithdraw 1.5\n")
        self.assertEqual(code, 2)
        self.assertIn("line 2", err)

    def test_negative_start_balance_is_refused_before_the_core(self) -> None:
        code, out, err = run_cli("deposit 1\n", "--start", "-5")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("start balance must be >= 0", err)


if __name__ == "__main__":
    unittest.main()
