import contextlib
import io
import unittest
from datetime import datetime

import cron_parser as cp


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cp.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class ParseTests(unittest.TestCase):
    def test_lists_ranges_steps(self):
        c = cp.parse("*/15 1-3 1,15 * *")
        self.assertEqual(c.minute.values, {0, 15, 30, 45})
        self.assertEqual(c.hour.values, {1, 2, 3})
        self.assertEqual(c.dom.values, {1, 15})
        self.assertEqual(c.month.values, set(range(1, 13)))
        self.assertEqual(cp.parse("10-20/5 * * * *").minute.values, {10, 15, 20})
        self.assertEqual(cp.parse("50/5 * * * *").minute.values, {50, 55})
        self.assertEqual(cp.parse("1-5,10,20-30/10 * * * *").minute.values,
                         {1, 2, 3, 4, 5, 10, 20, 30})
        self.assertEqual(cp.parse("* * * * */2").dow.values, {0, 2, 4, 6})

    def test_names(self):
        c = cp.parse("0 0 * JAN,Mar-may MON-fri")
        self.assertEqual(c.month.values, {1, 3, 4, 5})
        self.assertEqual(c.dow.values, {1, 2, 3, 4, 5})
        self.assertEqual(cp.parse("0 0 * * sun").dow.values, {0})
        self.assertEqual(cp.parse("0 0 * * 7").dow.values, {0})
        self.assertEqual(cp.parse("0 0 * * 5-7").dow.values, {5, 6, 0})
        self.assertEqual(cp.parse("0 0 * dec *").month.values, {12})


class CliTests(unittest.TestCase):
    def test_validate_explains_fields(self):
        code, out, err = run("validate", "*/15 9-17 * jan-mar mon-fri")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 5)
        for name in ("minute", "hour", "day-of-month", "month", "day-of-week"):
            self.assertIn(name, out)
        self.assertIn("jan, feb, mar", out)
        self.assertIn("0, 15, 30, 45", out)
        self.assertIn("every day-of-month", out)

    def test_validate_reports_errors(self):
        cases = [
            ("60 * * * *", "minute"),
            ("* 24 * * *", "hour"),
            ("* * 0 * *", "day-of-month"),
            ("* * * 13 *", "month"),
            ("* * * * 8", "day-of-week"),
            ("5-1 * * * *", "reversed"),
            ("*/0 * * * *", "step"),
            ("a * * * *", "invalid value"),
            ("* * * foo *", "month"),
            ("1,,2 * * * *", "empty"),
            ("* * * *", "expected 5 fields"),
            ("* * * * * *", "expected 5 fields"),
            ("*/x * * * *", "step"),
        ]
        for expr, needle in cases:
            code, out, err = run("validate", expr)
            self.assertEqual(code, 2, expr)
            self.assertIn(needle, err, expr)
            self.assertNotIn("Traceback", err)

    def test_validate_impossible_date(self):
        code, out, err = run("validate", "0 0 30 2 *")
        self.assertEqual(code, 2)
        self.assertIn("never matches", err)


FROM = "2026-10-31 10:30"


class NextTests(unittest.TestCase):
    def test_next_n_runs(self):
        code, out, _ = run("next", "*/20 * * * *", "-n", "4", "--from", FROM)
        self.assertEqual(code, 0)
        lines = [l[:16] for l in out.strip().splitlines()]
        self.assertEqual(lines, ["2026-10-31 10:40", "2026-10-31 11:00",
                                 "2026-10-31 11:20", "2026-10-31 11:40"])
        code, out, _ = run("next", "0 12 * * *", "--from", FROM)
        self.assertEqual(len(out.strip().splitlines()), 5)
        # strictly after start, even when start itself matches
        code, out, _ = run("next", "30 10 * * *", "-n", "1", "--from", FROM)
        self.assertTrue(out.startswith("2026-11-01 10:30"))
        # default start is now: results are in the future
        code, out, _ = run("next", "* * * * *", "-n", "2")
        self.assertEqual(code, 0)
        first = datetime.strptime(out.splitlines()[0][:16], "%Y-%m-%d %H:%M")
        self.assertGreater(first, datetime.now().replace(second=0, microsecond=0))
        code, _, err = run("next", "* * * * *", "-n", "0")
        self.assertEqual(code, 2)

    def test_next_each_matches(self):
        c = cp.parse("7,37 8-10 * 1,6 mon-wed")
        runs = cp.next_runs(c, datetime(2026, 1, 1), 40)
        self.assertEqual(runs, sorted(runs))
        self.assertEqual(len(set(runs)), 40)
        for r in runs:
            self.assertTrue(cp.matches(c, r))

    def test_impossible_dates(self):
        for expr in ("0 0 30 2 *", "0 0 31 4 *", "0 0 31 2,4,6,9,11 *"):
            code, out, err = run("next", expr, "--from", FROM)
            self.assertEqual(code, 2, expr)
            self.assertEqual(out, "")
            self.assertIn("never matches", err)
        # 31 alongside a valid month still works
        code, out, _ = run("next", "0 0 31 4,5 *", "-n", "1", "--from", FROM)
        self.assertTrue(out.startswith("2027-05-31"))
        # Feb 30 in a list with a real day only yields real days
        c = cp.parse("0 0 30,28 2 *")
        runs = cp.next_runs(c, datetime(2026, 1, 1), 3)
        self.assertEqual([r.day for r in runs], [28, 28, 28])

    def test_dom_dow_or_and_leap(self):
        # 13th OR Friday, both restricted
        c = cp.parse("0 0 13 * fri")
        runs = cp.next_runs(c, datetime(2026, 10, 31, 10, 30), 4)
        self.assertEqual([r.strftime("%m-%d") for r in runs],
                         ["11-06", "11-13", "11-20", "11-27"])
        # only one restricted: AND semantics with the star
        c = cp.parse("0 0 13 * *")
        runs = cp.next_runs(c, datetime(2026, 10, 31), 2)
        self.assertEqual([r.strftime("%m-%d") for r in runs], ["11-13", "12-13"])
        # Feb 29: leap years only, across the 2100 non-leap gap
        c = cp.parse("0 0 29 2 *")
        runs = cp.next_runs(c, datetime(2026, 1, 1), 3)
        self.assertEqual([r.year for r in runs], [2028, 2032, 2036])
        runs = cp.next_runs(c, datetime(2097, 1, 1), 1)
        self.assertEqual([r.year for r in runs], [2104])


if __name__ == "__main__":
    unittest.main()
