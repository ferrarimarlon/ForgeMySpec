import ast
import contextlib
import io
import json
import os
import statistics
import tempfile
import unittest

import csv_analytics as ca

DATA = "name,age,city\nann,30,NY\nbob,40,LA\ncy,,NY\ndee,20,SF\n"


class CsvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "d.csv")
        with open(self.path, "w") as fh:
            fh.write(DATA)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ca.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_read_csv(self):
        cols, rows = ca.read_csv(self.path)
        self.assertEqual(cols, ["name", "age", "city"])
        self.assertEqual(rows[0], {"name": "ann", "age": "30", "city": "NY"})
        self.assertEqual(len(rows), 4)
        code, _, err = self.run_cli(os.path.join(self.tmp.name, "nope.csv"))
        self.assertEqual(code, 2)
        self.assertIn("nope.csv", err)

    def test_column_stats(self):
        _, rows = ca.read_csv(self.path)
        s = ca.column_stats(rows, "age")
        self.assertEqual(s["count"], 3)
        self.assertEqual((s["min"], s["max"]), (20, 40))
        self.assertAlmostEqual(s["mean"], 30)
        self.assertEqual(s["median"], 30)
        self.assertAlmostEqual(s["stdev"], statistics.stdev([30, 40, 20]))
        single = ca.column_stats([{"x": "5"}], "x")
        self.assertIsNone(single["stdev"])
        self.assertEqual(single["count"], 1)
        t = ca.column_stats(rows, "city")
        self.assertEqual((t["count"], t["min"], t["max"]), (4, "LA", "SF"))
        self.assertIsNone(t["mean"])

    def test_filter_rows(self):
        cols, rows = ca.read_csv(self.path)
        self.assertEqual([r["name"] for r in ca.filter_rows(rows, ["age > 25"], cols)],
                         ["ann", "bob"])
        got = ca.filter_rows(rows, ["city == NY", "age >= 30"], cols)
        self.assertEqual([r["name"] for r in got], ["ann"])
        self.assertEqual(len(ca.filter_rows(rows, ["city != NY"], cols)), 2)
        self.assertEqual(self.run_cli(self.path, "-f", "age ~ 3")[0], 2)
        code, _, err = self.run_cli(self.path, "-f", "zip > 3")
        self.assertEqual(code, 2)
        self.assertIn("zip", err)

    def test_select_columns(self):
        code, out, _ = self.run_cli(self.path, "-c", "city", "age")
        self.assertEqual(code, 0)
        self.assertEqual(list(json.loads(out)["columns"]), ["city", "age"])
        code, _, err = self.run_cli(self.path, "-c", "bogus")
        self.assertEqual(code, 2)
        self.assertIn("bogus", err)

    def test_export_json(self):
        code, out, _ = self.run_cli(self.path, "-f", "age > 25")
        self.assertEqual(code, 0)
        rep = json.loads(out)
        self.assertEqual(rep["row_count"], 2)
        self.assertEqual(rep["columns"]["age"]["mean"], 35)
        dest = os.path.join(self.tmp.name, "r.json")
        code, out, _ = self.run_cli(self.path, "-o", dest)
        self.assertEqual((code, out), (0, ""))
        with open(dest) as fh:
            self.assertEqual(json.load(fh)["row_count"], 4)

    def test_stdlib_only(self):
        src = os.path.join(os.path.dirname(__file__), "..", "csv_analytics.py")
        with open(src) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        allowed = {"argparse", "csv", "json", "math", "statistics", "sys"}
        self.assertTrue(mods)
        self.assertTrue(mods <= allowed, mods)


if __name__ == "__main__":
    unittest.main()
