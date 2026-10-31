import ast
import contextlib
import io
import os
import unittest
from datetime import datetime

import cron_parser as cp

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cron_parser.py")


def run(argv, now=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cp.main(argv, now=now)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class ParseTests(unittest.TestCase):
    def test_field_syntax(self):
        f = cp.parse("*/15 0-6/2 1,15 * *")
        self.assertEqual(f[0], {0, 15, 30, 45})
        self.assertEqual(f[1], {0, 2, 4, 6})
        self.assertEqual(f[2], {1, 15})
        self.assertEqual(f[3], set(range(1, 13)))
        self.assertEqual(cp.parse("5/20 * * * *")[0], {5, 25, 45})
        self.assertEqual(cp.parse("1-3,10 * * * *")[0], {1, 2, 3, 10})
        bad = ["* * * *", "* * * * * *", "60 * * * *", "* 24 * * *", "* * 0 * *",
               "* * 32 * *", "* * * 13 *", "* * * * 8", "*/0 * * * *", "5-1 * * * *",
               "a * * * *", "1,,2 * * * *", "1- * * * *", "*/ * * * *", "1-2-3 * * * *",
               "-1 * * * *", "", "*/2/3 * * * *"]
        for e in bad:
            with self.assertRaises(cp.CronError, msg=e):
                cp.parse(e)

    def test_names(self):
        f = cp.parse("0 0 * JAN-MAR,dec mon-fri")
        self.assertEqual(f[3], {1, 2, 3, 12})
        self.assertEqual(f[4], {1, 2, 3, 4, 5})
        self.assertEqual(cp.parse("0 0 * * sun")[4], {0})
        self.assertEqual(cp.parse("0 0 * * 7")[4], {0})
        self.assertEqual(cp.parse("0 0 * Feb *")[3], {2})
        for e in ["0 0 * foo *", "0 0 * * funday", "0 0 * * MON-xyz"]:
            with self.assertRaises(cp.CronError, msg=e):
                cp.parse(e)


class NextTests(unittest.TestCase):
    def test_invalid_dates(self):
        now = datetime(2025, 1, 1, 0, 0)
        runs = cp.next_runs(cp.parse("0 0 29 2 *"), now, 2)
        self.assertEqual(runs, [datetime(2028, 2, 29), datetime(2032, 2, 29)])
        runs = cp.next_runs(cp.parse("0 0 31 * *"), now, 6)
        self.assertTrue(all(r.day == 31 for r in runs))
        self.assertNotIn(4, [r.month for r in runs])
        self.assertNotIn(2, [r.month for r in runs])
        with self.assertRaises(cp.CronError):
            cp.next_runs(cp.parse("0 0 30 2 *"), now, 1)
        with self.assertRaises(cp.CronError):
            cp.next_runs(cp.parse("0 0 31 4 *"), now, 1)

    def test_dom_dow_or(self):
        now = datetime(2025, 1, 1, 0, 0)  # Wednesday
        # 15th OR Friday
        runs = cp.next_runs(cp.parse("0 0 15 * fri"), now, 4)
        self.assertEqual(runs, [datetime(2025, 1, 3), datetime(2025, 1, 10),
                                datetime(2025, 1, 15), datetime(2025, 1, 17)])
        # only dom restricted
        runs = cp.next_runs(cp.parse("0 0 15 * *"), now, 2)
        self.assertEqual(runs, [datetime(2025, 1, 15), datetime(2025, 2, 15)])
        # only dow restricted
        runs = cp.next_runs(cp.parse("0 0 * * mon"), now, 2)
        self.assertEqual(runs, [datetime(2025, 1, 6), datetime(2025, 1, 13)])
        # dom impossible but dow restricted: dow still fires (Mondays in February)
        runs = cp.next_runs(cp.parse("0 0 30 2 mon"), now, 1)
        self.assertEqual(runs, [datetime(2025, 2, 3)])


class CliTests(unittest.TestCase):
    def test_validate(self):
        code, out, _ = run(["validate", "*/15 9-17 * jan,mar mon-fri"])
        self.assertEqual(code, 0)
        for label in ("minute", "hour", "day-of-month", "month", "day-of-week"):
            self.assertEqual(sum(1 for l in out.splitlines() if l.startswith(label)), 1, label)
        code, out, err = run(["validate", "0 25 * * *"])
        self.assertEqual(code, 1)
        self.assertIn("hour", out + err)
        code, out, err = run(["validate", "* * *"])
        self.assertEqual(code, 1)
        code, out, err = run(["validate", "0 0 30 2 *"])
        self.assertEqual(code, 1)
        self.assertIn("never", (out + err).lower())

    def test_next(self):
        now = datetime(2025, 1, 1, 10, 30, 45)
        code, out, _ = run(["next", "*/20 * * * *"], now=now)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().splitlines(), ["2025-01-01 10:40"])
        code, out, _ = run(["next", "0 12 * * *", "-n", "3"], now=now)
        self.assertEqual(out.strip().splitlines(),
                         ["2025-01-01 12:00", "2025-01-02 12:00", "2025-01-03 12:00"])
        # strictly after the current minute
        code, out, _ = run(["next", "30 10 * * *"], now=datetime(2025, 1, 1, 10, 30, 0))
        self.assertEqual(out.strip(), "2025-01-02 10:30")
        code, _, _ = run(["next", "* * * * *", "-n", "0"], now=now)
        self.assertEqual(code, 2)
        code, _, _ = run(["next", "* * * * *", "-n", "x"], now=now)
        self.assertEqual(code, 2)
        code, _, err = run(["next", "0 0 30 2 *"], now=now)
        self.assertEqual(code, 1)
        code, _, _ = run(["next", "bad"], now=now)
        self.assertEqual(code, 1)
        code, _, _ = run([], now=now)
        self.assertEqual(code, 2)


class StructureTests(unittest.TestCase):
    def test_stdlib_only(self):
        with open(SRC) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                self.assertEqual(n.level, 0)
                mods.add((n.module or "").split(".")[0])
        import importlib.util
        import sysconfig
        stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
        self.assertTrue(mods)
        for m in mods:
            spec = importlib.util.find_spec(m)
            self.assertIsNotNone(spec, m)
            origin = spec.origin
            self.assertTrue(origin in ("built-in", "frozen")
                            or os.path.realpath(origin).startswith(stdlib), m)


if __name__ == "__main__":
    unittest.main()
