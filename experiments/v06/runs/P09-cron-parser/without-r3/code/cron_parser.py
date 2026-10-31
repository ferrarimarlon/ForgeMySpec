#!/usr/bin/env python3
"""Cron expression parser: validate and compute upcoming run times.

Usage:
    cron_parser.py validate "<expr>"
    cron_parser.py next "<expr>" [-n N]

Supports 5 fields (minute hour day-of-month month day-of-week) with '*',
lists (1,2), ranges (1-5), steps (*/15, 1-30/5, 5/10) and month/day names.
Day-of-week accepts 0-7 (0 and 7 are Sunday). As in Vixie cron, if both
day-of-month and day-of-week are restricted, a date matches when EITHER does.
Times are in the local timezone.
"""
import argparse
import calendar
import sys
from datetime import datetime, timedelta

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

# name, min, max, names (value -> offset of first name)
FIELDS = [
    ("minute", 0, 59, None, 0),
    ("hour", 0, 23, None, 0),
    ("day-of-month", 1, 31, None, 0),
    ("month", 1, 12, MONTHS, 1),
    ("day-of-week", 0, 7, DAYS, 0),
]

# Max days per month (February allows 29 for leap years)
MAX_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

SEARCH_YEARS = 12  # covers the 8-year gap around non-leap century years


class CronError(ValueError):
    pass


class Field:
    def __init__(self, name, text, values, star):
        self.name = name
        self.text = text
        self.values = values  # sorted list of ints
        self.star = star      # starts with '*' (unrestricted for day matching)


def _parse_value(tok, fname, lo, hi, names, offset):
    t = tok.lower()
    if names and t in names:
        return names.index(t) + offset
    if not t.isdigit():
        hint = " (names allowed)" if names else ""
        raise CronError(f"{fname}: invalid value '{tok}'{hint}")
    v = int(t)
    if v < lo or v > hi:
        raise CronError(f"{fname}: value {v} out of range {lo}-{hi}")
    return v


def parse_field(text, spec):
    fname, lo, hi, names, offset = spec
    if text == "":
        raise CronError(f"{fname}: empty field")
    values = set()
    for part in text.split(","):
        if part == "":
            raise CronError(f"{fname}: empty list item in '{text}'")
        rng, sep, step_s = part.partition("/")
        step = 1
        if sep:
            if not step_s.isdigit() or int(step_s) == 0:
                raise CronError(f"{fname}: invalid step '{step_s}' (must be a positive integer)")
            step = int(step_s)
        if rng == "*":
            start, end = lo, hi
        elif "-" in rng:
            a, _, b = rng.partition("-")
            start = _parse_value(a, fname, lo, hi, names, offset)
            end = _parse_value(b, fname, lo, hi, names, offset)
            if start > end:
                raise CronError(f"{fname}: range '{rng}' is reversed")
        else:
            start = _parse_value(rng, fname, lo, hi, names, offset)
            end = hi if sep else start  # "5/10" means 5-max/10
        values.update(range(start, end + 1, step))
    if fname == "day-of-week":
        values = {v % 7 for v in values}
    return Field(fname, text, sorted(values), text.startswith("*"))


class Cron:
    def __init__(self, expr):
        parts = expr.split()
        if len(parts) != 5:
            raise CronError(f"expected 5 fields (minute hour day-of-month month "
                            f"day-of-week), got {len(parts)}")
        self.minute, self.hour, self.dom, self.month, self.dow = (
            parse_field(p, s) for p, s in zip(parts, FIELDS))
        self.notes = []
        self._check_dates()

    def _check_dates(self):
        """Reject or flag day-of-month/month combinations that never exist."""
        if self.dom.star:
            return
        possible = [(m, d) for m in self.month.values for d in self.dom.values
                    if d <= MAX_DAYS[m - 1]]
        if not possible:
            what = (f"day-of-month {','.join(map(str, self.dom.values))} never occurs in "
                    f"month(s) {','.join(MONTHS[m - 1].title() for m in self.month.values)}")
            if self.dow.star:
                raise CronError(what + "; the expression can never run")
            self.notes.append("warning: " + what + "; only day-of-week will trigger")
            return
        for m in self.month.values:
            bad = [d for d in self.dom.values if d > MAX_DAYS[m - 1]]
            if bad:
                self.notes.append(
                    f"note: day(s) {','.join(map(str, bad))} do not exist in "
                    f"{calendar.month_name[m]} and will be skipped")
        if 29 in self.dom.values and self.month.values == [2]:
            self.notes.append("note: February 29 only occurs in leap years")

    def _day_matches(self, d):
        if d.month not in self.month.values:
            return False
        dom_ok = d.day in self.dom.values
        dow_ok = (d.isoweekday() % 7) in self.dow.values
        if self.dom.star or self.dow.star:
            return dom_ok and dow_ok
        return dom_ok or dow_ok

    def next_runs(self, start, n):
        """Return up to n run times strictly after `start`."""
        t = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = t.date().replace(year=t.year + SEARCH_YEARS) if not (
            t.month == 2 and t.day == 29) else t.date().replace(year=t.year + SEARCH_YEARS, day=28)
        day = t.date()
        out = []
        while day <= limit and len(out) < n:
            if day.month not in self.month.values:
                # jump to first day of next month
                day = (day.replace(day=1) + timedelta(days=32)).replace(day=1)
                continue
            if self._day_matches(day):
                for h in self.hour.values:
                    for m in self.minute.values:
                        cand = datetime(day.year, day.month, day.day, h, m)
                        if cand >= t:
                            out.append(cand)
                            if len(out) == n:
                                return out
            day += timedelta(days=1)
        return out


def describe(f, spec):
    _, lo, hi, names, offset = spec
    def label(v):
        if f.name == "month":
            return calendar.month_name[v]
        if f.name == "day-of-week":
            return calendar.day_name[(v - 1) % 7]  # 0 -> Sunday
        return str(v)
    if f.name == "day-of-week" and f.text.strip("*") == "" :
        return "every day of the week"
    if f.values == list(range(lo if f.name != "day-of-week" else 0,
                              (hi if f.name != "day-of-week" else 6) + 1)):
        return f"every {f.name}"
    return f"{', '.join(label(v) for v in f.values)}"


def cmd_validate(args):
    try:
        c = Cron(args.expr)
    except CronError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1
    print(f"Valid cron expression: {args.expr}")
    for f, spec in zip((c.minute, c.hour, c.dom, c.month, c.dow), FIELDS):
        print(f"  {f.name:<13} {f.text:<12} -> {describe(f, spec)}")
    if not (c.dom.star or c.dow.star):
        print("  (day-of-month and day-of-week both restricted: runs when EITHER matches)")
    for n in c.notes:
        print("  " + n)
    return 0


def cmd_next(args):
    if args.n < 1:
        print("Error: -n must be at least 1", file=sys.stderr)
        return 2
    try:
        c = Cron(args.expr)
    except CronError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1
    runs = c.next_runs(datetime.now(), args.n)
    if not runs:
        print(f"No run times found within {SEARCH_YEARS} years.", file=sys.stderr)
        return 1
    for r in runs:
        print(r.strftime("%Y-%m-%d %H:%M (%a)"))
    if len(runs) < args.n:
        print(f"(only {len(runs)} run(s) found within {SEARCH_YEARS} years)", file=sys.stderr)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Cron expression parser")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="explain each field or report the error")
    v.add_argument("expr", help='cron expression, quoted, e.g. "*/15 9-17 * * mon-fri"')
    v.set_defaults(func=cmd_validate)
    n = sub.add_parser("next", help="print the next run times")
    n.add_argument("expr")
    n.add_argument("-n", type=int, default=5, help="number of runs (default 5)")
    n.set_defaults(func=cmd_next)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
