#!/usr/bin/env python3
"""Cron expression parser CLI (5-field standard cron, stdlib only).

Usage:
    cron_parser.py validate "<expr>"
    cron_parser.py next "<expr>" [-n N]
"""
import argparse
import sys
from datetime import datetime, timedelta, date

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

# name, min, max, names (value -> offset)
FIELDS = [
    ("minute", 0, 59, None),
    ("hour", 0, 23, None),
    ("day-of-month", 1, 31, None),
    ("month", 1, 12, {n: i + 1 for i, n in enumerate(MONTHS)}),
    ("day-of-week", 0, 7, {n: i for i, n in enumerate(DAYS)}),
]

# Max days per month (February allows 29 for leap years)
MAX_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


class CronError(ValueError):
    pass


def _value(tok, fname, lo, hi, names):
    t = tok.lower()
    if names and t in names:
        return names[t]
    if not t.isdigit():
        raise CronError(f"{fname}: invalid value '{tok}'")
    v = int(t)
    if v < lo or v > hi:
        raise CronError(f"{fname}: value {v} out of range {lo}-{hi}")
    return v


def parse_field(text, fname, lo, hi, names):
    """Return the sorted set of values matched by one field."""
    if text == "":
        raise CronError(f"{fname}: empty field")
    values = set()
    for part in text.split(","):
        if part == "":
            raise CronError(f"{fname}: empty list item in '{text}'")
        rng, sep, step_s = part.partition("/")
        step = 1
        if sep:
            if not step_s.isdigit() or int(step_s) < 1:
                raise CronError(f"{fname}: invalid step '{step_s}'")
            step = int(step_s)
        if rng == "*":
            start, end = lo, hi
        elif "-" in rng:
            a, _, b = rng.partition("-")
            start = _value(a, fname, lo, hi, names)
            end = _value(b, fname, lo, hi, names)
            if start > end:
                raise CronError(f"{fname}: range start {start} > end {end}")
        else:
            start = _value(rng, fname, lo, hi, names)
            end = hi if sep else start
        values.update(range(start, end + 1, step))
    return values


class CronExpr:
    def __init__(self, expr):
        parts = expr.split()
        if len(parts) != 5:
            raise CronError(f"expected 5 fields, got {len(parts)}")
        self.raw = parts
        sets = [parse_field(p, n, lo, hi, names)
                for p, (n, lo, hi, names) in zip(parts, FIELDS)]
        self.minutes, self.hours, self.doms, self.months, dows = sets
        self.dows = {d % 7 for d in dows}  # 7 == Sunday
        self.dom_star = parts[2].startswith("*")
        self.dow_star = parts[4].startswith("*")
        self._check_satisfiable()

    def _check_satisfiable(self):
        # Day-of-week restriction (alone or OR'd with dom) always matches some day.
        if not self.dow_star:
            return
        if not any(d <= MAX_DAYS[m - 1] for m in self.months for d in self.doms):
            raise CronError(
                "no valid date: day-of-month "
                f"{self.raw[2]} never occurs in month {self.raw[3]} "
                "(e.g. February 30 does not exist)")

    def day_matches(self, d):
        if d.month not in self.months:
            return False
        dom_ok = d.day in self.doms
        dow_ok = (d.isoweekday() % 7) in self.dows
        if self.dom_star or self.dow_star:
            return dom_ok and dow_ok  # a star side matches everything
        return dom_ok or dow_ok  # both restricted: classic cron OR

    def next_runs(self, start, n, max_years=10):
        """Yield up to n run times strictly after `start`."""
        t = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        day = t.date()
        end = day + timedelta(days=366 * max_years)
        hours, minutes = sorted(self.hours), sorted(self.minutes)
        found = 0
        first = True
        while day <= end and found < n:
            if self.day_matches(day):
                for h in hours:
                    for m in minutes:
                        cand = datetime(day.year, day.month, day.day, h, m)
                        if first and cand < t:
                            continue
                        yield cand
                        found += 1
                        if found >= n:
                            return
            first = False
            day += timedelta(days=1)


def describe(text, lo, hi, names, fname):
    if text == "*":
        return "every value"
    inv = {v: k for k, v in names.items()} if names else {}
    vals = sorted(parse_field(text, fname, lo, hi, names))
    if fname == "day-of-week":
        vals = sorted({v % 7 for v in vals})
    shown = [inv.get(v, str(v)).capitalize() if inv else str(v) for v in vals]
    return ", ".join(shown)


def cmd_validate(args):
    try:
        cron = CronExpr(args.expr)
    except CronError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1
    print(f"Valid cron expression: {args.expr}")
    for raw, (name, lo, hi, names) in zip(cron.raw, FIELDS):
        print(f"  {name:<13} {raw:<12} -> {describe(raw, lo, hi, names, name)}")
    if not cron.dom_star and not cron.dow_star:
        print("  note: both day fields restricted; runs when EITHER matches")
    return 0


def cmd_next(args):
    if args.n < 1:
        print("Error: -n must be >= 1", file=sys.stderr)
        return 1
    try:
        cron = CronExpr(args.expr)
    except CronError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1
    runs = list(cron.next_runs(datetime.now(), args.n))
    for r in runs:
        print(r.strftime("%Y-%m-%d %H:%M (%a)"))
    if len(runs) < args.n:
        print(f"Only {len(runs)} run(s) found within the next 10 years.",
              file=sys.stderr)
        return 1 if not runs else 0
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Cron expression parser")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate and explain an expression")
    v.add_argument("expr", help='quoted 5-field cron expression, e.g. "*/15 9-17 * * mon-fri"')
    v.set_defaults(func=cmd_validate)
    n = sub.add_parser("next", help="print next run times")
    n.add_argument("expr")
    n.add_argument("-n", type=int, default=5, help="number of runs (default 5)")
    n.set_defaults(func=cmd_next)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
