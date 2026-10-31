import ast
import contextlib
import io
import json
import os
import random
import sys
import tempfile
import unittest

import expense_splitter as es


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = es.main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class SplitTests(unittest.TestCase):
    def test_shares_sum_exactly(self):
        shares = es.split_shares(1000, ["c", "a", "b"])
        self.assertEqual(sum(shares.values()), 1000)
        self.assertEqual(shares, {"a": 334, "b": 333, "c": 333})
        for amount in (1, 2, 99, 10001):
            for n in range(1, 8):
                s = es.split_shares(amount, ["p%d" % i for i in range(n)])
                self.assertEqual(sum(s.values()), amount)
                self.assertLessEqual(max(s.values()) - min(s.values()), 1)

    def test_parse_amount(self):
        self.assertEqual(es.parse_amount("42.5"), 4250)
        self.assertEqual(es.parse_amount("0.07"), 7)
        for bad in ("0", "-3", "1.234", "abc", "", "nan", "1e3"):
            with self.assertRaises(es.LedgerError):
                es.parse_amount(bad)


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.json")
            self.assertEqual(es.load(path), [])
            code, _, _ = run_cli("--file", path, "add", "--payer", "ann", "--amount", "30",
                                 "--description", "dinner", "--participants", "ann", "bob")
            self.assertEqual(code, 0)
            with open(path) as f:
                raw = json.load(f)
            self.assertEqual(raw["expenses"][0]["amount_cents"], 3000)
            self.assertEqual(es.load(path), raw["expenses"])
            run_cli("--file", path, "add", "--payer", "bob", "--amount", "5",
                    "--description", "tea", "--participants", "ann", "bob")
            self.assertEqual(len(es.load(path)), 2)


class BalanceTests(unittest.TestCase):
    def test_balances_sum_to_zero(self):
        ex = [es.make_expense("ann", "30", "a", ["ann", "bob", "cy"]),
              es.make_expense("bob", "10.01", "b", ["bob", "cy"]),
              es.make_expense("dan", "7", "c", ["ann"])]
        bal = es.balances(ex)
        self.assertEqual(sum(bal.values()), 0)
        self.assertEqual(bal["ann"], 3000 - 1000 - 700)
        self.assertEqual(bal["dan"], 700)


class SettleTests(unittest.TestCase):
    def test_plan_zeroes_balances(self):
        bal = {"a": 5000, "b": -3000, "c": -2000}
        plan = es.settle_plan(bal)
        self.assertEqual(plan, [("b", "a", 3000), ("c", "a", 2000)])
        rng = random.Random(1)
        for _ in range(200):
            n = rng.randint(2, 8)
            vals = [rng.randint(-5000, 5000) for _ in range(n - 1)]
            vals.append(-sum(vals))
            bal = {"p%d" % i: v for i, v in enumerate(vals)}
            plan = es.settle_plan(bal)
            self.assertLessEqual(len(plan), n - 1)
            after = dict(bal)
            for d, c, amt in plan:
                self.assertGreater(amt, 0)
                after[d] += amt
                after[c] -= amt
            self.assertTrue(all(v == 0 for v in after.values()))

    def test_largest_pairs_first(self):
        plan = es.settle_plan({"a": 100, "b": 900, "c": -400, "d": -600})
        self.assertEqual(plan[0], ("d", "b", 600))


class CliTests(unittest.TestCase):
    def test_invalid_input_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.json")
            run_cli("--file", path, "add", "--payer", "ann", "--amount", "10",
                    "--description", "ok", "--participants", "ann")
            before = open(path).read()
            for amount in ("abc", "-5", "1.999"):
                code, _, err = run_cli("--file", path, "add", "--payer", "ann", "--amount", amount,
                                       "--description", "x", "--participants", "ann")
                self.assertEqual(code, 2)
                self.assertIn("error", err)
            code, _, _ = run_cli("--file", path, "add", "--payer", "ann", "--amount", "5",
                                 "--description", "x", "--participants", " ")
            self.assertEqual(code, 2)
            self.assertEqual(open(path).read(), before)
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write("{not json")
            for cmd in (["balances"], ["settle"], ["list"]):
                code, _, err = run_cli("--file", bad, *cmd)
                self.assertEqual(code, 2)
            code, _, _ = run_cli("--file", bad, "add", "--payer", "a", "--amount", "1",
                                 "--description", "x", "--participants", "a")
            self.assertEqual(code, 2)
            self.assertEqual(open(bad).read(), "{not json")

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.json")
            run_cli("--file", path, "add", "--payer", "ann", "--amount", "30",
                    "--description", "dinner", "--participants", "ann", "bob", "cy")
            code, out, _ = run_cli("--file", path, "balances")
            self.assertEqual(out.splitlines(), ["ann: 20.00", "bob: -10.00", "cy: -10.00"])
            code, out, _ = run_cli("--file", path, "settle")
            self.assertEqual(out.splitlines(), ["bob pays ann 10.00", "cy pays ann 10.00"])


class StructureTests(unittest.TestCase):
    def test_stdlib_only_imports(self):
        tree = ast.parse(open(es.__file__, encoding="utf-8").read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        self.assertTrue(mods)
        if hasattr(sys, "stdlib_module_names"):
            self.assertTrue(mods <= set(sys.stdlib_module_names), mods)
        else:  # Python < 3.10: stdlib modules live next to the os module
            import importlib.util
            stdlib_dir = os.path.dirname(os.__file__)
            for m in mods:
                spec = importlib.util.find_spec(m)
                origin = spec.origin or ""
                self.assertTrue(origin in ("built-in", "frozen") or origin.startswith(stdlib_dir)
                                and "site-packages" not in origin, m)


if __name__ == "__main__":
    unittest.main()
