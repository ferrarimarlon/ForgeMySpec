import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import budget_tracker


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "d.json")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = budget_tracker.main(["--file", self.path, *argv])
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def raw(self):
        with open(self.path) as fh:
            return fh.read()

    def test_set_budget_persists(self):
        self.assertEqual(self.run_cli("set-budget", "food", "100")[0], 0)
        self.assertEqual(json.loads(self.raw())["budgets"], {"food": "100.00"})
        self.assertNotEqual(self.run_cli("set-budget", "food", "0")[0], 0)

    def test_add_persists_expense(self):
        self.run_cli("set-budget", "food", "100")
        code, _, _ = self.run_cli("add", "12.50", "food", "--date", "2026-03-05", "--note", "lunch")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.raw())["expenses"],
                         [{"amount": "12.50", "category": "food", "date": "2026-03-05", "note": "lunch"}])

    def test_unknown_category_rejected(self):
        self.run_cli("set-budget", "food", "100")
        before = self.raw()
        code, _, err = self.run_cli("add", "5", "games", "--date", "2026-03-05")
        self.assertNotEqual(code, 0)
        self.assertIn("unknown category", err)
        self.assertEqual(self.raw(), before)

    def test_invalid_amount_rejected(self):
        self.run_cli("set-budget", "food", "100")
        before = self.raw()
        for bad in ["abc", "0", "-5", "nan", "inf", "1.234", ""]:
            code, _, _ = self.run_cli("add", bad, "food", "--date", "2026-03-05")
            self.assertNotEqual(code, 0, bad)
        code, _, _ = self.run_cli("add", "5", "food", "--date", "2026-13-40")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.raw(), before)
        self.assertNotEqual(self.run_cli("set-budget", "x", "-1")[0], 0)

    def test_report_per_category(self):
        self.run_cli("set-budget", "food", "100")
        self.run_cli("set-budget", "fun", "50")
        self.run_cli("add", "25", "food", "--date", "2026-03-05")
        self.run_cli("add", "70", "food", "--date", "2026-04-05")
        code, out, _ = self.run_cli("report", "--month", "2026-03")
        self.assertEqual(code, 0)
        food = [l for l in out.splitlines() if l.startswith("food")][0]
        self.assertIn("25.00", food)
        self.assertIn("100.00", food)
        self.assertIn("25.0%", food)
        self.assertIn("0.0%", [l for l in out.splitlines() if l.startswith("fun")][0])

    def test_alert_at_80_percent(self):
        self.run_cli("set-budget", "food", "100")
        _, out, _ = self.run_cli("add", "79.99", "food", "--date", "2026-03-01")
        self.assertNotIn("WARNING", out)
        _, out, _ = self.run_cli("add", "0.01", "food", "--date", "2026-03-02")
        self.assertIn("WARNING", out)
        self.assertNotIn("ALERT", out)
        _, rep, _ = self.run_cli("report", "--month", "2026-03")
        self.assertIn("WARNING", rep)

    def test_alert_at_100_percent(self):
        self.run_cli("set-budget", "food", "100")
        _, out, _ = self.run_cli("add", "99.99", "food", "--date", "2026-03-01")
        self.assertNotIn("ALERT", out)
        _, out, _ = self.run_cli("add", "0.01", "food", "--date", "2026-03-02")
        self.assertIn("ALERT: over budget", out)
        _, rep, _ = self.run_cli("report", "--month", "2026-03")
        self.assertIn("ALERT", rep)

    def test_stdlib_only_imports(self):
        with open(budget_tracker.__file__) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        allowed = {"argparse", "datetime", "json", "os", "sys", "decimal"}
        self.assertTrue(mods <= allowed, mods)


if __name__ == "__main__":
    unittest.main()
