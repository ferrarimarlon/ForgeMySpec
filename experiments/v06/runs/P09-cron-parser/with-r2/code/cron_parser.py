#!/usr/bin/env python3
"""Cron expression parser CLI: validate and next. Standard library only."""
import argparse
import calendar
import datetime as dt
import sys

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

# name, low, high, names -> value map
FIELDS = [
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day-of-month", 1, 31, {}),
    ("month", 1, 12, {n: i + 1 for i, n in enumerate(MONTHS)}),
    ("day-of-week", 0, 7, {n: i for i, n in enumerate(DAYS)}),
]

SEARCH_YEARS = 10  # covers the longest gap (Feb 29 across a skipped century leap year)


class CronError(ValueError):
    pass


class Schedule:
    def __init__(self, sets, dom_star, dow_star):
        (self.minutes, self.hours, self.doms, self.months, self.dows) = sets
        self.dom_star = dom_star
        self.dow_star = dow_star

    def day_matches(self, day):
        if day.month not in self.months:
            return False
        dom = day.day in self.doms
        dow = (day.isoweekday() % 7) in self.dows
        if self.dom_star or self.dow_star:
            return dom and dow
        return dom or dow


def _value(token, name, lo, hi, names):
    if not token:
        raise CronError(f"{name}: empty value")
    if token.isascii() and token.isdigit():
        v = int(token)
    elif token.upper() in names:
        v = names[token.upper()]
    else:
        raise CronError(f"{name}: invalid value '{token}'")
    if not lo <= v <= hi:
        raise CronError(f"{name}: value {v} out of range {lo}-{hi}")
    return v


def parse_field(text, name, lo, hi, names):
    """Return the set of values selected by one field."""
    result = set()
    for part in text.split(","):
        if not part:
            raise CronError(f"{name}: empty list item in '{text}'")
        base, slash, step_text = part.partition("/")
        step = 1
        if slash:
            if not (step_text.isascii() and step_text.isdigit()):
                raise CronError(f"{name}: invalid step '{step_text}'")
            step = int(step_text)
            if step == 0:
                raise CronError(f"{name}: step must be greater than 0")
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start = _value(a, name, lo, hi, names)
            end = _value(b, name, lo, hi, names)
            if start > end:
                raise CronError(f"{name}: reversed range '{base}'")
        else:
            start = _value(base, name, lo, hi, names)
            end = hi if slash else start
        result.update(range(start, end + 1, step))
    return result


def parse(expr):
    parts = expr.split()
    if len(parts) != 5:
        raise CronError(f"expected 5 fields, got {len(parts)}")
    sets = []
    for text, (name, lo, hi, names) in zip(parts, FIELDS):
        sets.append(parse_field(text, name, lo, hi, names))
    sets[4] = {v % 7 for v in sets[4]}  # 7 is Sunday
    return Schedule(sets, parts[2].startswith("*"), parts[4].startswith("*")), parts


def next_runs(schedule, after, n):
    """Up to n run times strictly after `after` (minute resolution)."""
    start = after.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    day = start.date()
    last = day.replace(year=day.year + SEARCH_YEARS) if not (
        day.month == 2 and day.day == 29) else day.replace(year=day.year + SEARCH_YEARS, day=28)
    minutes, hours = sorted(schedule.minutes), sorted(schedule.hours)
    out = []
    while day <= last and len(out) < n:
        if schedule.day_matches(day):
            for h in hours:
                for m in minutes:
                    t = dt.datetime(day.year, day.month, day.day, h, m)
                    if t >= start:
                        out.append(t)
                        if len(out) == n:
                            return out
        day += dt.timedelta(days=1)
    return out


def _describe_values(values, name, lo, hi):
    if name == "day-of-week":
        labels = [DAYS[v] for v in sorted(values)]
    elif name == "month":
        labels = [MONTHS[v - 1] for v in sorted(values)]
    else:
        labels = [str(v) for v in sorted(values)]
    if len(values) == hi - lo + 1 or (name == "day-of-week" and len(values) == 7):
        return "every value"
    return ", ".join(labels)


def explain(expr):
    schedule, parts = parse(expr)
    sets = [schedule.minutes, schedule.hours, schedule.doms, schedule.months, schedule.dows]
    lines = []
    for text, vals, (name, lo, hi, _) in zip(parts, sets, FIELDS):
        lines.append(f"{name:<13} {text:<12} {_describe_values(vals, name, lo, hi)}")
    return lines


def main(argv=None, now=None, out=None):
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="cron_parser", description="Cron expression parser")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="explain each field or report the error")
    v.add_argument("expr", nargs="+", help="5-field cron expression")
    nx = sub.add_parser("next", help="print the next run times")
    nx.add_argument("expr", nargs="+", help="5-field cron expression")
    nx.add_argument("-n", type=int, default=5, help="number of run times (default 5)")
    args = ap.parse_args(argv)
    expr = " ".join(args.expr)

    try:
        if args.cmd == "validate":
            for line in explain(expr):
                print(line, file=out)
            schedule, _ = parse(expr)
            if not next_runs(schedule, now or dt.datetime.now(), 1):
                print("note: this expression never matches a real date", file=out)
            return 0
        if args.n < 1:
            raise CronError("-n must be at least 1")
        schedule, _ = parse(expr)
        runs = next_runs(schedule, now or dt.datetime.now(), args.n)
        if not runs:
            raise CronError("expression never matches a real date "
                            f"(searched {SEARCH_YEARS} years)")
        for t in runs:
            print(f"{t:%Y-%m-%d %H:%M} {calendar.day_abbr[t.weekday()]}", file=out)
        return 0
    except CronError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
