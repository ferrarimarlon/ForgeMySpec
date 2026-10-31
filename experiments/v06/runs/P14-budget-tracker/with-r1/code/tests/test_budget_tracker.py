import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import budget_tracker

SRC = budget_tracker.__file__


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "b.json")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = budget_tracker.main(["--file", self.path, *argv])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def read(self):
        with open(self.path) as fh:
            return json.load(fh)

    def test_set_budget_persists(self):
        self.assertEqual(self.run_cli("set-budget", "food", "200")[0], 0)
        self.assertEqual(self.read()["budgets"], {"food": "200.00"})
        self.run_cli("set-budget", "food", "250.50")
        self.assertEqual(self.read()["budgets"], {"food": "250.50"})

    def test_add_expense_persists(self):
        self.run_cli("set-budget", "food", "200")
        code, _, _ = self.run_cli("add", "12.34", "food", "--date", "2026-03-05", "--note", "lunch")
        self.assertEqual(code, 0)
        self.assertEqual(self.read()["expenses"], [
            {"amount": "12.34", "category": "food", "date": "2026-03-05", "note": "lunch"}])

    def test_unknown_category_rejected(self):
        self.run_cli("set-budget", "food", "200")
        before = open(self.path).read()
        code, _, err = self.run_cli("add", "5", "travel", "--date", "2026-03-05")
        self.assertEqual(code, 2)
        self.assertIn("travel", err)
        self.assertEqual(open(self.path).read(), before)

    def test_invalid_amount_rejected(self):
        self.run_cli("set-budget", "food", "200")
        before = open(self.path).read()
        for bad in ["0", "-5", "abc", "nan", "inf", "-inf", "1.234", "", "1e2x"]:
            for argv in (("add", "--date", "2026-03-05", "--", bad, "food"), ("set-budget", "--", "food", bad)):
                code, _, err = self.run_cli(*argv)
                self.assertEqual(code, 2, (bad, argv))
                self.assertIn("invalid amount", err)
                self.assertEqual(open(self.path).read(), before)

    def test_report_per_category(self):
        self.run_cli("set-budget", "food", "200")
        self.run_cli("set-budget", "fun", "100")
        self.run_cli("add", "50", "food", "--date", "2026-03-01")
        self.run_cli("add", "25", "food", "--date", "2026-03-31")
        self.run_cli("add", "999", "food", "--date", "2026-04-01")
        code, out, _ = self.run_cli("report", "--month", "2026-03")
        self.assertEqual(code, 0)
        food = next(l for l in out.splitlines() if l.startswith("food"))
        fun = next(l for l in out.splitlines() if l.startswith("fun"))
        self.assertIn("75.00", food)
        self.assertIn("200.00", food)
        self.assertIn("37.5%", food)
        self.assertIn("0.00", fun)
        self.assertIn("0.0%", fun)

    def test_alert_at_80_percent(self):
        self.run_cli("set-budget", "food", "100")
        _, out, _ = self.run_cli("add", "79.99", "food", "--date", "2026-03-01")
        self.assertNotIn("WARNING", out)
        _, out, _ = self.run_cli("add", "0.01", "food", "--date", "2026-03-02")
        self.assertIn("WARNING", out)
        self.assertNotIn("EXCEEDED", out)
        _, out, _ = self.run_cli("report", "--month", "2026-03")
        self.assertIn("WARNING", out)
        self.assertNotIn("EXCEEDED", out)

    def test_alert_at_100_percent(self):
        self.run_cli("set-budget", "food", "100")
        _, out, _ = self.run_cli("add", "99.99", "food", "--date", "2026-03-01")
        self.assertNotIn("EXCEEDED", out)
        _, out, _ = self.run_cli("add", "0.01", "food", "--date", "2026-03-02")
        self.assertIn("EXCEEDED", out)
        _, out, _ = self.run_cli("report", "--month", "2026-03")
        self.assertIn("EXCEEDED", out)

    def test_stdlib_only_imports(self):
        with open(SRC) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        allowed = getattr(sys, "stdlib_module_names", None) or {
            "argparse", "json", "os", "sys", "datetime", "decimal"}
        self.assertTrue(mods <= set(allowed), mods)


if __name__ == "__main__":
    unittest.main()
