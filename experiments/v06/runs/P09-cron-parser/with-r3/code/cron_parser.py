#!/usr/bin/env python3
"""Cron expression parser CLI: ``validate`` and ``next`` for 5-field expressions.

Fields: minute hour day-of-month month day-of-week. Supports ``*``, lists
(``1,2``), ranges (``1-5``), steps (``*/5``, ``1-10/2``, ``5/15``), and
month/day names (``jan``, ``MON-FRI``). Day-of-week 0 and 7 are Sunday. When
both day-of-month and day-of-week are restricted, either matching is enough.
"""
import argparse
import calendar
import sys
from datetime import date, datetime, timedelta

MONTH_NAMES = ["jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec"]
DAY_NAMES = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

# name, min, max, names -> offset of first name's numeric value
FIELDS = [
    ("minute", 0, 59, None, 0),
    ("hour", 0, 23, None, 0),
    ("day-of-month", 1, 31, None, 0),
    ("month", 1, 12, MONTH_NAMES, 1),
    ("day-of-week", 0, 7, DAY_NAMES, 0),
]

MAX_GAP_YEARS = 8


class CronError(ValueError):
    """Invalid cron expression; carries the offending field name."""

    def __init__(self, field, message):
        super().__init__("%s: %s" % (field, message))
        self.field = field
        self.message = message


class Field:
    def __init__(self, name, text, values, restricted):
        self.name = name
        self.text = text
        self.values = values          # frozenset of ints (day-of-week: 0-6)
        self.restricted = restricted  # False when the field starts with '*'


class CronExpression:
    def __init__(self, text, fields):
        self.text = text
        self.minute, self.hour, self.dom, self.month, self.dow = fields

    @property
    def fields(self):
        return [self.minute, self.hour, self.dom, self.month, self.dow]


def _parse_value(field, token, lo, hi, names, offset):
    low = token.lower()
    if names is not None and low in names:
        return names.index(low) + offset
    if not token.isascii() or not token.isdigit():
        raise CronError(field, "invalid value %r" % token)
    value = int(token)
    if value < lo or value > hi:
        raise CronError(field, "value %d out of range %d-%d" % (value, lo, hi))
    return value


def parse_field(name, text, lo, hi, names=None, offset=0):
    """Parse one field into a Field. Raises CronError."""
    if text == "":
        raise CronError(name, "empty field")
    values = set()
    for item in text.split(","):
        if item == "":
            raise CronError(name, "empty list item in %r" % text)
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not step_text.isascii() or not step_text.isdigit():
                raise CronError(name, "invalid step %r" % step_text)
            step = int(step_text)
            if step == 0:
                raise CronError(name, "step must be greater than 0")
        if base == "*":
            start, end = lo, hi
            if name == "day-of-week":
                end = 6
        elif "-" in base:
            left, _, right = base.partition("-")
            start = _parse_value(name, left, lo, hi, names, offset)
            end = _parse_value(name, right, lo, hi, names, offset)
            if start > end:
                raise CronError(name, "range %s is reversed" % base)
        else:
            start = _parse_value(name, base, lo, hi, names, offset)
            end = hi if slash else start
        values.update(range(start, end + 1, step))
    if name == "day-of-week":
        values = {v % 7 for v in values}
    return Field(name, text, frozenset(values), not text.startswith("*"))


def parse(expr):
    """Parse a 5-field cron expression into a CronExpression. Raises CronError."""
    parts = expr.split()
    if len(parts) != 5:
        raise CronError("expression",
                        "expected 5 fields, got %d" % len(parts))
    fields = [parse_field(n, p, lo, hi, names, off)
              for p, (n, lo, hi, names, off) in zip(parts, FIELDS)]
    return CronExpression(" ".join(parts), fields)


def _days_in_month_max(month):
    return 29 if month == 2 else calendar.monthrange(2001, month)[1]


def can_ever_match(cron):
    """False if no real calendar date can match (e.g. February 30)."""
    if cron.dom.restricted and not cron.dow.restricted:
        return any(d <= _days_in_month_max(m)
                   for m in cron.month.values for d in cron.dom.values)
    return bool(cron.month.values)


def _day_matches(cron, day):
    if day.month not in cron.month.values:
        return False
    dom_ok = day.day in cron.dom.values
    dow_ok = (day.weekday() + 1) % 7 in cron.dow.values
    if cron.dom.restricted and cron.dow.restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def matches(cron, dt):
    return (dt.minute in cron.minute.values and dt.hour in cron.hour.values
            and _day_matches(cron, dt.date()))


def next_runs(cron, start, count):
    """Return up to ``count`` run times strictly after ``start``."""
    if not can_ever_match(cron):
        return []
    first = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    hours = sorted(cron.hour.values)
    minutes = sorted(cron.minute.values)
    results = []
    day = first.date()
    last_hit = day
    while len(results) < count:
        if (day - last_hit).days > 366 * MAX_GAP_YEARS:
            break
        if day.year > 9998:
            break
        if _day_matches(cron, day):
            for h in hours:
                for m in minutes:
                    dt = datetime(day.year, day.month, day.day, h, m)
                    if dt >= first:
                        results.append(dt)
                        last_hit = day
                        if len(results) == count:
                            return results
        day += timedelta(days=1)
    return results


def _label(field, value):
    if field.name == "month":
        return MONTH_NAMES[value - 1]
    if field.name == "day-of-week":
        return DAY_NAMES[value]
    return str(value)


def describe_field(field, lo, hi):
    total = hi - lo + 1 if field.name != "day-of-week" else 7
    if len(field.values) == total:
        return "every %s" % field.name
    vals = ", ".join(_label(field, v) for v in sorted(field.values))
    return "%s in %s" % (field.name, vals)


def explain(cron):
    lines = []
    for field, (name, lo, hi, _, _) in zip(cron.fields, FIELDS):
        lines.append("%-13s %-12s %s" % (name, field.text,
                                         describe_field(field, lo, hi)))
    return lines


def _parse_from(text):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError("invalid --from %r (use 'YYYY-MM-DD HH:MM')" % text)


def _never_message(cron):
    return ("%r is syntactically valid but never matches a real date "
            "(e.g. February 30)" % cron.text)


def cmd_validate(args):
    cron = parse(args.expr)
    for line in explain(cron):
        print(line)
    if not can_ever_match(cron):
        print("error: " + _never_message(cron), file=sys.stderr)
        return 2
    return 0


def cmd_next(args):
    if args.n < 1:
        raise ValueError("-n must be at least 1")
    cron = parse(args.expr)
    if not can_ever_match(cron):
        print("error: " + _never_message(cron), file=sys.stderr)
        return 2
    start = _parse_from(args.start) if args.start else datetime.now()
    runs = next_runs(cron, start, args.n)
    for dt in runs:
        print(dt.strftime("%Y-%m-%d %H:%M (%a)"))
    if not runs:
        print("error: no run times found", file=sys.stderr)
        return 2
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="cron_parser",
                                description="Parse 5-field cron expressions.")
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="explain each field or report the error")
    v.add_argument("expr", help="cron expression, quoted: '*/5 * * * *'")
    v.set_defaults(func=cmd_validate)
    n = sub.add_parser("next", help="print the next N run times")
    n.add_argument("expr", help="cron expression, quoted")
    n.add_argument("-n", type=int, default=5, help="how many runs (default 5)")
    n.add_argument("--from", dest="start", default=None,
                   help=argparse.SUPPRESS)
    n.set_defaults(func=cmd_next)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (CronError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
