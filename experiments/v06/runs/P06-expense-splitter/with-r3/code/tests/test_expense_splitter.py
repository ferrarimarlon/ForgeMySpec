import ast
import contextlib
import io
import json
import os
import tempfile
import unittest

import expense_splitter as es


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "e.json")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = es.main(["--file", self.path, *argv], out=out)
        return code, out.getvalue(), err.getvalue()

    def add(self, payer, amount, participants, desc="x"):
        code, _, err = self.run_cli("add", "--payer", payer, "--amount", amount,
                                    "--description", desc, "--participants", *participants)
        self.assertEqual(code, 0, err)


class AddTests(Base):
    def test_add_records_expense(self):
        self.add("alice", "30.00", ["alice", "bob"], "dinner")
        with open(self.path) as f:
            data = json.load(f)
        self.assertEqual(data["expenses"], [{"payer": "alice", "amount_cents": 3000,
                                             "description": "dinner",
                                             "participants": ["alice", "bob"]}])

    def test_persists_across_invocations(self):
        self.add("alice", "10", ["alice", "bob"])
        self.add("bob", "5.50", ["alice", "bob"])
        self.assertEqual(len(es.load(self.path)), 2)
        code, out, _ = self.run_cli("balances")
        self.assertEqual(out, "alice: 2.25\nbob: -2.25\n")

    def test_comma_separated_participants(self):
        self.add("a", "9", ["a,b,c"])
        self.assertEqual(es.load(self.path)[0]["participants"], ["a", "b", "c"])


class SplitTests(unittest.TestCase):
    def test_equal_split_sums_to_amount(self):
        for cents in (1, 2, 100, 1000, 9999):
            for n in range(1, 8):
                names = ["p%d" % i for i in range(n)]
                shares = list(es.split_equally(cents, names).values())
                self.assertEqual(sum(shares), cents)
                self.assertLessEqual(max(shares) - min(shares), 1)


class BalanceTests(Base):
    def test_balances_sum_to_zero(self):
        self.add("a", "10.00", ["a", "b", "c"])
        self.add("b", "7.01", ["a", "b"])
        self.add("d", "3", ["a", "c"])
        bal = es.compute_balances(es.load(self.path))
        self.assertEqual(sum(bal.values()), 0)
        self.assertEqual(bal["d"], 300)


class SettleTests(Base):
    def test_settlement_zeroes_balances(self):
        self.add("a", "100", ["a", "b", "c", "d"])
        self.add("b", "40.50", ["a", "b", "c"])
        self.add("c", "12.34", ["b", "c", "d"])
        bal = es.compute_balances(es.load(self.path))
        plan = es.settle(bal)
        nonzero = sum(1 for v in bal.values() if v)
        self.assertLessEqual(len(plan), nonzero - 1)
        for d, c, amt in plan:
            self.assertGreater(amt, 0)
            bal[d] += amt
            bal[c] -= amt
        self.assertTrue(all(v == 0 for v in bal.values()))

    def test_greedy_picks_largest_pair(self):
        plan = es.settle({"a": 500, "b": 200, "c": -300, "d": -400})
        self.assertEqual(plan[0], ("d", "a", 400))

    def test_settle_cli(self):
        self.add("a", "10", ["a", "b"])
        self.assertEqual(self.run_cli("settle")[1], "b pays a 5.00\n")

    def test_settle_empty(self):
        self.assertEqual(self.run_cli("settle")[1], "All settled.\n")


class ErrorTests(Base):
    def test_invalid_input_leaves_file_unchanged(self):
        self.add("a", "10", ["a", "b"])
        with open(self.path, "rb") as f:
            before = f.read()
        bad = [
            ("a", "abc", ["a"]), ("a", "-5", ["a"]), ("a", "0", ["a"]),
            ("a", "1.005", ["a"]), ("a", "nan", ["a"]), ("a", "10", [","]),
            ("a", "10", ["a", "a"]), (" ", "10", ["a"]),
        ]
        for payer, amount, parts in bad:
            code, _, err = self.run_cli("add", "--payer", payer, "--amount", amount,
                                        "--participants", *parts)
            self.assertEqual(code, 2, (payer, amount, parts))
            self.assertIn("error:", err)
            with open(self.path, "rb") as f:
                self.assertEqual(f.read(), before)

    def test_corrupt_json_rejected_and_untouched(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        for argv in (["balances"], ["settle"],
                     ["add", "--payer", "a", "--amount", "1", "--participants", "a"]):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2)
            self.assertIn("error:", err)
        with open(self.path) as f:
            self.assertEqual(f.read(), "{not json")

    def test_malformed_structure_rejected(self):
        with open(self.path, "w") as f:
            json.dump({"expenses": [{"payer": "a"}]}, f)
        self.assertEqual(self.run_cli("balances")[0], 2)


class StructureTests(unittest.TestCase):
    def test_stdlib_only(self):
        with open(es.__file__) as f:
            tree = ast.parse(f.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        self.assertLessEqual(mods, {"argparse", "json", "os", "sys", "tempfile", "decimal"})


if __name__ == "__main__":
    unittest.main()
