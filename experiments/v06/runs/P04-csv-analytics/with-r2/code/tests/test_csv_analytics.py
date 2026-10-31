import ast
import contextlib
import io
import json
import os
import statistics
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv_analytics as ca

SAMPLE = "name,age,city\nann,30,rio\nbob,25,sao\ncid,35,rio\ndee,,sao\n"


def write(text):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.csv")
    with open(p, "w") as f:
        f.write(text)
    return p


class ReadTests(unittest.TestCase):
    def test_read_csv(self):
        header, rows = ca.read_csv(write(SAMPLE))
        self.assertEqual(header, ["name", "age", "city"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0], {"name": "ann", "age": "30", "city": "rio"})
        with self.assertRaises(ca.CsvAnalyticsError):
            ca.read_csv("/nonexistent/x.csv")
        with self.assertRaises(ca.CsvAnalyticsError):
            ca.read_csv(write(""))
        self.assertEqual(ca.main(["/nonexistent/x.csv"]), 2)


class StatsTests(unittest.TestCase):
    def test_numeric_stats(self):
        header, rows = ca.read_csv(write(SAMPLE))
        s = ca.column_stats(header, rows)["age"]
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["min"], 25)
        self.assertEqual(s["max"], 35)
        self.assertEqual(s["mean"], 30)
        self.assertEqual(s["median"], 30)
        self.assertAlmostEqual(s["stdev"], statistics.stdev([30, 25, 35]))
        n = ca.column_stats(header, rows)["name"]
        self.assertEqual((n["count"], n["min"], n["max"], n["mean"]), (4, "ann", "dee", None))
        one = ca.column_stats(["x"], [{"x": "5"}])["x"]
        self.assertIsNone(one["stdev"])


class FilterTests(unittest.TestCase):
    def test_filter_rows(self):
        header, rows = ca.read_csv(write(SAMPLE))
        names = lambda rs: [r["name"] for r in rs]
        self.assertEqual(names(ca.filter_rows(rows, ["age>=30"], header)), ["ann", "cid"])
        self.assertEqual(names(ca.filter_rows(rows, ["city == rio", "age > 30"], header)), ["cid"])
        self.assertEqual(names(ca.filter_rows(rows, ["city != rio"], header)), ["bob", "dee"])
        self.assertEqual(names(ca.filter_rows(rows, ["age < 30"], header)), ["bob"])
        self.assertEqual(names(ca.filter_rows(rows, ["age<=25"], header)), ["bob"])
        self.assertEqual(len(ca.filter_rows(rows, [], header)), 4)
        with self.assertRaises(ca.CsvAnalyticsError):
            ca.filter_rows(rows, ["zip == 1"], header)
        with self.assertRaises(ca.CsvAnalyticsError):
            ca.filter_rows(rows, ["nonsense"], header)


class SelectTests(unittest.TestCase):
    def test_select_columns(self):
        header, rows = ca.read_csv(write(SAMPLE))
        h, r = ca.select_columns(header, rows, ["city", "name"])
        self.assertEqual(h, ["city", "name"])
        self.assertEqual(list(r[0].keys()), ["city", "name"])
        with self.assertRaises(ca.CsvAnalyticsError):
            ca.select_columns(header, rows, ["nope"])


class ReportTests(unittest.TestCase):
    def test_cli_report(self):
        p = write(SAMPLE)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ca.main([p, "--select", "age,city", "--filter", "city == rio"])
        self.assertEqual(rc, 0)
        rep = json.loads(out.getvalue())
        self.assertEqual(rep["row_count"], 2)
        self.assertEqual(rep["total_rows"], 4)
        self.assertEqual(rep["columns"], ["age", "city"])
        self.assertEqual(rep["stats"]["age"]["mean"], 32.5)
        dest = os.path.join(os.path.dirname(p), "r.json")
        self.assertEqual(ca.main([p, "--output", dest]), 0)
        with open(dest) as f:
            self.assertIn("stats", json.load(f))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(ca.main([p, "--select", "zzz"]), 2)


class ConstraintTests(unittest.TestCase):
    def test_stdlib_only(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "csv_analytics.py")
        with open(path) as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        allowed = {"argparse", "csv", "json", "math", "operator", "re", "statistics", "sys"}
        self.assertTrue(mods <= allowed, mods)


if __name__ == "__main__":
    unittest.main()
