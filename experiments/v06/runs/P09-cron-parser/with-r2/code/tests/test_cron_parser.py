import ast
import datetime as dt
import io
import os
import unittest
from contextlib import redirect_stderr

import cron_parser as cp

NOW = dt.datetime(2024, 1, 31, 12, 0, 30)


def run(argv, now=NOW):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stderr(err):
        code = cp.main(argv, now=now, out=out)
    return code, out.getvalue(), err.getvalue()


def field(text, i):
    name, lo, hi, names = cp.FIELDS[i]
    return cp.parse_field(text, name, lo, hi, names)


class FieldTests(unittest.TestCase):
    def test_five_fields_required(self):
        cp.parse("* * * * *")
        for bad in ["", "* * * *", "* * * * * *"]:
            with self.assertRaises(cp.CronError) as c:
                cp.parse(bad)
            self.assertIn("expected 5 fields", str(c.exception))

    def test_syntax_forms(self):
        self.assertEqual(field("*", 0), set(range(60)))
        self.assertEqual(field("5", 0), {5})
        self.assertEqual(field("1,3,5", 0), {1, 3, 5})
        self.assertEqual(field("10-12", 1), {10, 11, 12})
        self.assertEqual(field("*/15", 0), {0, 15, 30, 45})
        self.assertEqual(field("10-20/5", 0), {10, 15, 20})
        self.assertEqual(field("50/5", 0), {50, 55})
        self.assertEqual(field("1-3,10,20-30/5", 0), {1, 2, 3, 10, 20, 25, 30})
        for text, i in [("60", 0), ("24", 1), ("0", 2), ("32", 2), ("13", 3),
                        ("8", 4), ("*/0", 0), ("5-1", 0), ("a", 0), ("1,,2", 0),
                        ("*/x", 0), ("-1", 0), ("1-", 0)]:
            with self.assertRaises(cp.CronError, msg=text):
                field(text, i)

    def test_names(self):
        self.assertEqual(field("jan,Dec", 3), {1, 12})
        self.assertEqual(field("MAR-MAY", 3), {3, 4, 5})
        self.assertEqual(field("mon-fri", 4), {1, 2, 3, 4, 5})
        self.assertEqual(field("SUN,sat", 4), {0, 6})
        s, _ = cp.parse("0 0 * * 7")
        self.assertEqual(s.dows, {0})
        s, _ = cp.parse("0 0 * * 5-7")
        self.assertEqual(s.dows, {5, 6, 0})
        with self.assertRaises(cp.CronError):
            field("MON", 3)


class NextTests(unittest.TestCase):
    def runs(self, expr, n=5, now=NOW):
        s, _ = cp.parse(expr)
        return cp.next_runs(s, now, n)

    def test_next_runs(self):
        r = self.runs("*/20 * * * *", 4)
        self.assertEqual(r, [dt.datetime(2024, 1, 31, 12, m) for m in (20, 40)]
                         + [dt.datetime(2024, 1, 31, 13, m) for m in (0, 20)])
        self.assertEqual(len(self.runs("* * * * *")), 5)
        self.assertEqual(self.runs("0 12 * * *", 1), [dt.datetime(2024, 2, 1, 12, 0)])
        # strictly after: exact match at now is excluded
        self.assertEqual(self.runs("0 12 * * *", 1, dt.datetime(2024, 1, 31, 12, 0)),
                         [dt.datetime(2024, 2, 1, 12, 0)])
        r = self.runs("30 9 * * mon-fri", 3, dt.datetime(2024, 2, 2, 10, 0))  # Friday
        self.assertEqual([t.day for t in r], [5, 6, 7])
        # dom and dow both restricted: either matches
        r = self.runs("0 0 15 * fri", 3, dt.datetime(2024, 3, 1, 0, 0))
        self.assertEqual([t.day for t in r], [8, 15, 22])
        self.assertEqual(self.runs("0 0 * * *", 3), sorted(self.runs("0 0 * * *", 3)))

    def test_invalid_dates(self):
        self.assertEqual(self.runs("0 0 30 2 *"), [])
        self.assertEqual(self.runs("0 0 31 4,6,9,11 *"), [])
        r = self.runs("0 0 29 2 *", 3, dt.datetime(2023, 1, 1))
        self.assertEqual([t.year for t in r], [2024, 2028, 2032])
        self.assertTrue(all(t.month == 2 and t.day == 29 for t in r))
        r = self.runs("0 0 31 * *", 4, dt.datetime(2024, 1, 1))
        self.assertEqual([t.month for t in r], [1, 3, 5, 7])
        # century gap: 2096 -> 2104
        r = self.runs("0 0 29 2 *", 1, dt.datetime(2097, 1, 1))
        self.assertEqual(r[0].year, 2104)
        code, out, err = run(["next", "0 0 30 2 *"])
        self.assertEqual(code, 1)
        self.assertIn("never matches", err)
        self.assertEqual(out, "")


class CliTests(unittest.TestCase):
    def test_validate_explains_fields(self):
        code, out, _ = run(["validate", "*/15 9-17 1,15 jan-mar mon-fri"])
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 5)
        for line, name in zip(lines, ["minute", "hour", "day-of-month", "month", "day-of-week"]):
            self.assertTrue(line.startswith(name))
        self.assertIn("0, 15, 30, 45", lines[0])
        self.assertIn("JAN, FEB, MAR", lines[3])
        self.assertIn("MON, TUE, WED, THU, FRI", lines[4])

    def test_validate_reports_errors(self):
        for expr, needle in [("60 * * * *", "minute"), ("* 24 * * *", "hour"),
                             ("* * 0 * *", "day-of-month"), ("* * * 13 *", "month"),
                             ("* * * * 8", "day-of-week"), ("*/0 * * * *", "minute"),
                             ("* * * * 5-1", "day-of-week"), ("* * * foo *", "month"),
                             ("* * *", "5 fields")]:
            code, out, err = run(["validate", expr])
            self.assertNotEqual(code, 0, expr)
            self.assertIn(needle, err, expr)
        code, out, _ = run(["validate", "0 0 30 2 *"])
        self.assertEqual(code, 0)
        self.assertIn("never matches", out)

    def test_next_cli(self):
        code, out, _ = run(["next", "0 0 * * *", "-n", "2"])
        self.assertEqual(out.splitlines(), ["2024-02-01 00:00 Thu", "2024-02-02 00:00 Fri"])
        self.assertEqual(len(run(["next", "* * * * *"])[1].splitlines()), 5)
        self.assertEqual(run(["next", "* * * * *", "-n", "0"])[0], 1)

    def test_stdlib_only(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "cron_parser.py")
        with open(path) as f:
            tree = ast.parse(f.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods <= {"argparse", "calendar", "datetime", "sys"}, mods)


if __name__ == "__main__":
    unittest.main()
