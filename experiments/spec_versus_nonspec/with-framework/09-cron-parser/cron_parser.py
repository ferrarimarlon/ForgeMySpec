#!/usr/bin/env python3
"""Cron Expression Parser CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: 5-field, expand to sets, iterate minute-by-minute, skip invalid dates.
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Set

FIELD_SPECS = [
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("dom", 1, 31),
    ("month", 1, 12),
    ("dow", 0, 6),
]


def parse_field(field_str: str, min_val: int, max_val: int) -> Set[int]:
    """Parse a cron field into a set of integers."""
    result = set()
    for part in field_str.split(","):
        part = part.strip()
        if part == "*":
            result.update(range(min_val, max_val + 1))
        elif "/" in part:
            # step: */N or A-B/N or A/N
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"Step must be positive, got {step}")
            if base == "*":
                candidates = range(min_val, max_val + 1)
            elif "-" in base:
                a, b = base.split("-", 1)
                candidates = range(int(a), int(b) + 1)
            else:
                a = int(base)
                candidates = range(a, max_val + 1)
            result.update(v for i, v in enumerate(candidates) if i % step == 0)
        elif "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a), int(b) + 1))
        else:
            result.add(int(part))
    # Validate all values in range
    invalid = [v for v in result if v < min_val or v > max_val]
    if invalid:
        raise ValueError(f"Values {invalid} out of range [{min_val}, {max_val}]")
    return result


def parse_cron(expr: str):
    """Parse 5-field cron expression. Returns (min_set, hr_set, dom_set, mon_set, dow_set)."""
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Expected 5 fields, got {len(fields)}: '{expr}'")
    sets = []
    for i, (name, mn, mx) in enumerate(FIELD_SPECS):
        s = parse_field(fields[i], mn, mx)
        sets.append(s)
    return tuple(sets)


def matches(dt: datetime, min_set, hr_set, dom_set, mon_set, dow_set) -> bool:
    """Check if datetime matches cron sets."""
    return (
        dt.minute in min_set
        and dt.hour in hr_set
        and dt.day in dom_set
        and dt.month in mon_set
        and dt.weekday() in {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}[dt.weekday()] and True
    )


def next_times(expr: str, count: int = 5, from_dt: datetime = None) -> List[datetime]:
    """Compute the next `count` execution times after `from_dt`."""
    min_set, hr_set, dom_set, mon_set, dow_set = parse_cron(expr)
    if from_dt is None:
        from_dt = datetime.now()
    # Start from next minute
    current = from_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    results = []
    limit = 366 * 24 * 60  # max iterations
    iterations = 0
    while len(results) < count and iterations < limit:
        iterations += 1
        try:
            # Check validity (catches invalid dates like Feb 30)
            _ = current.year  # basic check
            # dow mapping: Python weekday() 0=Mon...6=Sun; cron 0=Sun...6=Sat
            cron_dow = (current.weekday() + 1) % 7  # 0=Sun, 1=Mon, ..., 6=Sat
            if (current.minute in min_set
                    and current.hour in hr_set
                    and current.day in dom_set
                    and current.month in mon_set
                    and cron_dow in dow_set):
                results.append(current)
        except ValueError:
            pass
        current += timedelta(minutes=1)
    return results


def cmd_next(args: argparse.Namespace) -> None:
    count = args.count
    from_dt = None
    if args.from_time:
        try:
            from_dt = datetime.strptime(args.from_time, "%Y-%m-%dT%H:%M")
        except ValueError:
            print(f"Error: invalid --from format. Use YYYY-MM-DDTHH:MM", file=sys.stderr)
            sys.exit(1)
    try:
        times = next_times(args.cron_expr, count=count, from_dt=from_dt)
    except ValueError as e:
        print(f"Error parsing cron expression: {e}", file=sys.stderr)
        sys.exit(1)
    if not times:
        print("No matching times found (expression may never fire).")
        return
    for t in times:
        print(t.strftime("%Y-%m-%d %H:%M"))


def cmd_validate(args: argparse.Namespace) -> None:
    try:
        sets = parse_cron(args.cron_expr)
        print(f"Valid cron expression: '{args.cron_expr}'")
        labels = ["minute", "hour", "day-of-month", "month", "day-of-week"]
        for label, s in zip(labels, sets):
            sorted_vals = sorted(s)
            print(f"  {label}: {sorted_vals}")
    except ValueError as e:
        print(f"Invalid: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cron Expression Parser CLI")
    sub = parser.add_subparsers(dest="command")

    p_next = sub.add_parser("next", help="Compute next N execution times")
    p_next.add_argument("cron_expr", help="Cron expression (5 fields, quoted)")
    p_next.add_argument("--count", type=int, default=5, help="Number of times to show")
    p_next.add_argument("--from", dest="from_time", help="Start from datetime (YYYY-MM-DDTHH:MM)")

    p_val = sub.add_parser("validate", help="Validate a cron expression")
    p_val.add_argument("cron_expr", help="Cron expression")

    args = parser.parse_args()
    if args.command == "next":
        cmd_next(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
