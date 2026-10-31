import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import csv_analytics  # noqa: E402

CSV = "name,age,score,city\nann,30,1.5,rome\nbob,40,2.5,oslo\ncy,50,,rome\ndee,20,4.0,lima\n"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = csv_analytics.main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "data.csv")
        with open(self.path, "w", newline="") as f:
            f.write(CSV)


class StatsTests(Base):
    def test_numeric_column_stats(self):
        code, out, _ = run_cli([self.path])
        self.assertEqual(code, 0)
        cols = json.loads(out)["columns"]
        age = cols["age"]
        self.assertEqual(age["count"], 4)
        self.assertEqual(age["min"], 20)
        self.assertEqual(age["max"], 50)
        self.assertAlmostEqual(age["mean"], 35)
        self.assertAlmostEqual(age["median"], 35)
        self.assertAlmostEqual(age["stdev"], 12.909944487358056)
        score = cols["score"]  # empty cell excluded
        self.assertEqual(score["count"], 3)
        self.assertAlmostEqual(score["median"], 2.5)
        self.assertAlmostEqual(score["mean"], 8 / 3)
        city = cols["city"]
        self.assertEqual(city["count"], 4)
        self.assertIsNone(city["mean"])
        self.assertIsNone(city["stdev"])

    def test_single_value_stdev_null(self):
        rows = [{"x": "5"}]
        self.assertIsNone(csv_analytics.column_stats(rows, ["x"])["x"]["stdev"])


class FilterTests(Base):
    def test_filters_are_anded(self):
        code, out, _ = run_cli(
            [self.path, "--filter", "age>=30", "--filter", "city==rome"])
        self.assertEqual(code, 0)
        rep = json.loads(out)
        self.assertEqual(rep["rows"], 2)
        self.assertEqual(rep["columns"]["age"]["min"], 30)
        self.assertEqual(rep["columns"]["age"]["max"], 50)

    def test_filter_string_compare(self):
        code, out, _ = run_cli([self.path, "--filter", "name != ann"])
        self.assertEqual(json.loads(out)["rows"], 3)


class SelectTests(Base):
    def test_selected_columns_only(self):
        code, out, _ = run_cli([self.path, "--columns", "age,city"])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(json.loads(out)["columns"]), ["age", "city"])
        code, _, err = run_cli([self.path, "--columns", "nope"])
        self.assertEqual(code, 2)
        self.assertIn("nope", err)


class ReportTests(Base):
    def test_json_report_written(self):
        outp = os.path.join(self.tmp.name, "r.json")
        code, out, _ = run_cli([self.path, "--output", outp])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        with open(outp) as f:
            rep = json.load(f)
        self.assertEqual(rep["rows"], 4)
        self.assertIn("age", rep["columns"])


class ErrorTests(Base):
    def test_bad_input_exits_2(self):
        for argv in ([os.path.join(self.tmp.name, "missing.csv")],
                     [self.path, "--filter", "garbage"],
                     [self.path, "--filter", "nope>1"]):
            code, out, err = run_cli(argv)
            self.assertEqual(code, 2, argv)
            self.assertTrue(err.strip())
            self.assertNotIn("Traceback", err)


class StructureTests(unittest.TestCase):
    def test_stdlib_only_single_file(self):
        path = os.path.join(ROOT, "csv_analytics.py")
        with open(path) as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                names.add(node.module.split(".")[0])
        self.assertTrue(names)
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is not None:
            self.assertTrue(names <= set(stdlib), names)
            return
        import importlib.util
        import sysconfig
        std_dir = os.path.realpath(sysconfig.get_paths()["stdlib"])
        for n in names:
            spec = importlib.util.find_spec(n)
            origin = getattr(spec, "origin", None)
            self.assertIsNotNone(spec, n)
            if origin in (None, "built-in", "frozen"):
                continue
            self.assertTrue(os.path.realpath(origin).startswith(std_dir)
                            and "site-packages" not in origin, (n, origin))


if __name__ == "__main__":
    unittest.main()
