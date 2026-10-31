#!/usr/bin/env python3
"""Cron expression parser CLI: validate and compute next run times."""
import argparse
import calendar
import sys
from datetime import datetime, timedelta

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

# name, min, max, names (name -> value)
FIELDS = [
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day-of-month", 1, 31, {}),
    ("month", 1, 12, {m: i + 1 for i, m in enumerate(MONTHS)}),
    ("day-of-week", 0, 7, {d: i for i, d in enumerate(DAYS)}),
]

MAX_YEARS = 10  # covers the longest gap between leap days (8 years)


class CronError(ValueError):
    pass


def _value(tok, fname, lo, hi, names):
    t = tok.lower()
    if t in names:
        return names[t]
    if not t.isdigit():
        raise CronError(f"{fname}: invalid value '{tok}'")
    v = int(t)
    if not lo <= v <= hi:
        raise CronError(f"{fname}: {v} out of range {lo}-{hi}")
    return v


def parse_field(text, fname, lo, hi, names):
    """Return the set of values matched by one field."""
    if not text:
        raise CronError(f"{fname}: empty field")
    result = set()
    for part in text.split(","):
        if not part:
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
                raise CronError(f"{fname}: range {rng} is reversed")
        else:
            start = _value(rng, fname, lo, hi, names)
            end = hi if sep else start  # "5/10" means 5-max step 10
        result.update(range(start, end + 1, step))
    return result


class CronExpr:
    def __init__(self, expr):
        parts = expr.split()
        if len(parts) != 5:
            raise CronError(f"expected 5 fields, got {len(parts)}")
        self.parts = parts
        sets = [parse_field(p, n, lo, hi, names)
                for p, (n, lo, hi, names) in zip(parts, FIELDS)]
        self.minutes, self.hours, self.doms, self.months, dows = sets
        self.dows = {d % 7 for d in dows}  # 7 == Sunday
        self.dom_star = parts[2].startswith("*")
        self.dow_star = parts[4].startswith("*")

    def day_matches(self, d):
        if d.month not in self.months:
            return False
        dom_ok = d.day in self.doms
        dow_ok = (d.isoweekday() % 7) in self.dows
        # Standard cron: if both day fields are restricted, either may match.
        if not self.dom_star and not self.dow_star:
            return dom_ok or dow_ok
        return dom_ok and dow_ok

    def next_runs(self, start, n):
        """Yield up to n run times strictly after `start`."""
        start = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        day = start.date()
        last = day.replace(year=day.year + MAX_YEARS) if not (
            day.month == 2 and day.day == 29) else day.replace(year=day.year + MAX_YEARS, day=28)
        times = [(h, m) for h in sorted(self.hours) for m in sorted(self.minutes)]
        found = 0
        while day <= last and found < n:
            if self.day_matches(day):
                for h, m in times:
                    t = datetime(day.year, day.month, day.day, h, m)
                    if t >= start:
                        yield t
                        found += 1
                        if found >= n:
                            return
            day += timedelta(days=1)


def describe(text, vals, fname, lo, hi, names):
    if text == "*":
        return f"every {fname}"
    shown = sorted(vals)
    if fname == "month":
        shown = [calendar.month_name[v] for v in shown]
    elif fname == "day-of-week":
        shown = [calendar.day_name[(v - 1) % 7] for v in shown]
        shown = list(dict.fromkeys(shown))
    else:
        shown = [str(v) for v in shown]
    return "at " + ", ".join(shown) if len(shown) <= 12 else \
        f"{len(shown)} values ({shown[0]}..{shown[-1]})"


def cmd_validate(args):
    try:
        cron = CronExpr(args.expr)
    except CronError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1
    print(f"Valid cron expression: {args.expr}")
    sets = [cron.minutes, cron.hours, cron.doms, cron.months, cron.dows]
    for part, vals, (n, lo, hi, names) in zip(cron.parts, sets, FIELDS):
        if n == "day-of-week":
            vals = {(v if v else 0) for v in vals}
        print(f"  {n:<13} {part:<12} {describe(part, vals, n, lo, hi, names)}")
    if next(cron.next_runs(datetime.now(), 1), None) is None:
        print(f"Warning: this expression never matches a real date "
              f"(within {MAX_YEARS} years).")
    return 0


def cmd_next(args):
    if args.n < 1:
        print("Error: -n must be at least 1", file=sys.stderr)
        return 1
    try:
        cron = CronExpr(args.expr)
    except CronError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1
    runs = list(cron.next_runs(datetime.now(), args.n))
    if not runs:
        print(f"No run times found within {MAX_YEARS} years "
              f"(the expression may name a nonexistent date, e.g. Feb 30).",
              file=sys.stderr)
        return 1
    for t in runs:
        print(t.strftime("%Y-%m-%d %H:%M (%a)"))
    if len(runs) < args.n:
        print(f"Only {len(runs)} run(s) found within {MAX_YEARS} years.",
              file=sys.stderr)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Cron expression parser")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="explain each field or report the error")
    v.add_argument("expr", help='quoted 5-field expression, e.g. "*/15 9-17 * * mon-fri"')
    v.set_defaults(func=cmd_validate)
    n = sub.add_parser("next", help="print the next run times from now")
    n.add_argument("expr")
    n.add_argument("-n", type=int, default=5, help="number of runs (default 5)")
    n.set_defaults(func=cmd_next)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
