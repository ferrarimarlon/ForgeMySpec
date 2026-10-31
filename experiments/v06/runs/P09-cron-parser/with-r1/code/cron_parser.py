#!/usr/bin/env python3
"""Standard 5-field cron expression parser: `validate` and `next` subcommands."""
import argparse
import sys
from datetime import datetime, timedelta

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

# label, min, max, names (name -> value)
FIELDS = [
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day-of-month", 1, 31, {}),
    ("month", 1, 12, {n: i + 1 for i, n in enumerate(MONTHS)}),
    ("day-of-week", 0, 7, {n: i for i, n in enumerate(DAYS)}),
]
SEARCH_DAYS = 366 * 8  # longest gap between matching dates (Feb 29 across a skipped leap year)


class CronError(ValueError):
    pass


class Cron(list):
    """Five sets of allowed values; dom_star/dow_star record an unrestricted day field."""
    dom_star = True
    dow_star = True
    raw = ()


def _value(tok, label, lo, hi, names):
    t = tok.upper()
    if t in names:
        return names[t]
    if t.isascii() and t.isdigit():
        v = int(t)
        if lo <= v <= hi:
            return v
        raise CronError(f"invalid {label}: {tok!r} is out of range {lo}-{hi}")
    raise CronError(f"invalid {label}: unrecognized value {tok!r}")


def _parse_part(part, label, lo, hi, names):
    if part == "":
        raise CronError(f"invalid {label}: empty list item")
    base, sep, step_s = part.partition("/")
    step = 1
    if sep:
        if not (step_s.isascii() and step_s.isdigit()) or int(step_s) < 1:
            raise CronError(f"invalid {label}: bad step {step_s!r} in {part!r}")
        step = int(step_s)
        if "/" in step_s:
            raise CronError(f"invalid {label}: bad step in {part!r}")
    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        a, _, b = base.partition("-")
        start, end = _value(a, label, lo, hi, names), _value(b, label, lo, hi, names)
        if start > end:
            raise CronError(f"invalid {label}: reversed range {base!r}")
    else:
        start = _value(base, label, lo, hi, names)
        end = hi if sep else start
    return set(range(start, end + 1, step))


def parse_field(text, index):
    label, lo, hi, names = FIELDS[index]
    values = set()
    for part in text.split(","):
        values |= _parse_part(part, label, lo, hi, names)
    if index == 4:
        values = {v % 7 for v in values}
    return values


def parse(expr):
    parts = expr.split()
    if len(parts) != 5:
        raise CronError(f"expected 5 fields, got {len(parts)}")
    cron = Cron(parse_field(p, i) for i, p in enumerate(parts))
    cron.raw = tuple(parts)
    cron.dom_star = parts[2].startswith("*")
    cron.dow_star = parts[4].startswith("*")
    return cron


def _day_matches(cron, d):
    if d.month not in cron[3]:
        return False
    dom = d.day in cron[2]
    dow = (d.weekday() + 1) % 7 in cron[4]
    if cron.dom_star or cron.dow_star:
        return dom and dow
    return dom or dow


def next_runs(cron, now, n):
    """The next n run times strictly after `now` (minute resolution)."""
    start = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    hours, minutes = sorted(cron[1]), sorted(cron[0])
    runs = []
    day = start.replace(hour=0, minute=0)
    idle = 0
    while len(runs) < n:
        if idle > SEARCH_DAYS:
            raise CronError("expression never matches any date")
        idle += 1
        if _day_matches(cron, day):
            for h in hours:
                for m in minutes:
                    t = day.replace(hour=h, minute=m)
                    if t >= start:
                        runs.append(t)
                        idle = 0
                        if len(runs) == n:
                            return runs
        day += timedelta(days=1)
    return runs


def _name(index, v):
    label = FIELDS[index][0]
    if label == "month":
        return MONTHS[v - 1].title()
    if label == "day-of-week":
        return DAYS[v].title()
    return str(v)


def explain(cron):
    lines = []
    for i, (label, lo, hi, _) in enumerate(FIELDS):
        vals = sorted(cron[i])
        full = set(range(lo, 7 if i == 4 else hi + 1))
        if set(vals) == full:
            text = f"every {label}"
        else:
            text = "at " + ", ".join(_name(i, v) for v in vals)
        lines.append(f"{label:<13}: {cron.raw[i]}  ({text})")
    return lines


def main(argv=None, now=None):
    ap = argparse.ArgumentParser(prog="cron_parser", description="Parse 5-field cron expressions.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="explain each field or report the error")
    v.add_argument("expr")
    nx = sub.add_parser("next", help="print the next run times")
    nx.add_argument("expr")
    nx.add_argument("-n", type=int, default=1, help="number of run times (default 1)")
    args = ap.parse_args(argv)
    if args.cmd == "next" and args.n < 1:
        ap.error("-n must be at least 1")
    now = now or datetime.now()
    try:
        cron = parse(args.expr)
        if args.cmd == "validate":
            next_runs(cron, now, 1)  # reports expressions that can never match (e.g. Feb 30)
            print("\n".join(explain(cron)))
        else:
            for t in next_runs(cron, now, args.n):
                print(t.strftime("%Y-%m-%d %H:%M"))
    except CronError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
