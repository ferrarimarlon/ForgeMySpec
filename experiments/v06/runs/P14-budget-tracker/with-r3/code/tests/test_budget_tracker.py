import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import budget_tracker as bt


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "data.json")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = bt.main(["--file", self.path, *argv], out)
        return code, out.getvalue(), err.getvalue()

    def raw(self):
        with open(self.path) as fh:
            return fh.read()


class BudgetTests(Base):
    def test_budget_persisted(self):
        self.assertEqual(self.run_cli("set-budget", "2026-10", "food", "200")[0], 0)
        data = json.loads(self.raw())
        self.assertEqual(data["budgets"]["2026-10"]["food"], "200.00")
        self.assertEqual(bt.budget_for(bt.load(self.path), "food", "2026-10"), bt.Decimal("200.00"))


class ExpenseTests(Base):
    def setUp(self):
        super().setUp()
        self.run_cli("set-budget", "2026-10", "food", "100")

    def test_expense_saved(self):
        code, _, _ = self.run_cli("add", "12.50", "food", "2026-10-03", "lunch")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.raw())["expenses"],
                         [{"amount": "12.50", "category": "food", "date": "2026-10-03", "note": "lunch"}])

    def test_unknown_category_rejected(self):
        before = self.raw()
        code, _, err = self.run_cli("add", "5", "travel", "2026-10-03", "x")
        self.assertNotEqual(code, 0)
        self.assertIn("unknown category", err)
        self.assertEqual(self.raw(), before)

    def test_invalid_amount_rejected(self):
        before = self.raw()
        for bad in ["0", "-5", "abc", "NaN", "inf", "Infinity", "1.234", ""]:
            code, _, err = self.run_cli("add", bad, "food", "2026-10-03", "x")
            self.assertNotEqual(code, 0, bad)
            self.assertIn("invalid amount", err)
            self.assertEqual(self.raw(), before)


class ReportTests(Base):
    def test_report_per_category(self):
        self.run_cli("set-budget", "2026-10", "food", "100")
        self.run_cli("set-budget", "2026-10", "fun", "50")
        self.run_cli("add", "10", "food", "2026-10-01", "")
        self.run_cli("add", "15.50", "food", "2026-10-02", "")
        self.run_cli("add", "99", "food", "2026-09-30", "")
        code, out, _ = self.run_cli("report", "2026-10")
        self.assertEqual(code, 0)
        food = [l for l in out.splitlines() if l.startswith("food")][0]
        self.assertIn("25.50", food)
        self.assertIn("100.00", food)
        self.assertIn("25.5%", food)
        fun = [l for l in out.splitlines() if l.startswith("fun")][0]
        self.assertIn("0.0%", fun)


class AlertTests(Base):
    def test_alert_thresholds(self):
        D = bt.Decimal
        b = D("100")
        self.assertIsNone(bt.alert_level(D("79.99"), b))
        self.assertEqual(bt.alert_level(D("80"), b), "warning")
        self.assertEqual(bt.alert_level(D("99.99"), b), "warning")
        self.assertEqual(bt.alert_level(D("100"), b), "exceeded")
        self.assertEqual(bt.alert_level(D("150"), b), "exceeded")
        self.run_cli("set-budget", "2026-10", "food", "100")
        _, out, _ = self.run_cli("add", "79", "food", "2026-10-01", "")
        self.assertNotIn("ALERT", out)
        _, out, _ = self.run_cli("add", "1", "food", "2026-10-02", "")
        self.assertIn("80%", out)
        _, out, _ = self.run_cli("add", "20", "food", "2026-10-03", "")
        self.assertIn("exceeded", out)
        _, rep, _ = self.run_cli("report", "2026-10")
        self.assertIn("exceeded", rep)


class StructureTests(unittest.TestCase):
    def test_stdlib_only(self):
        with open(bt.__file__) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        stdlib = {"argparse", "json", "os", "sys", "datetime", "decimal"}
        self.assertTrue(mods <= stdlib, mods)


if __name__ == "__main__":
    unittest.main()
