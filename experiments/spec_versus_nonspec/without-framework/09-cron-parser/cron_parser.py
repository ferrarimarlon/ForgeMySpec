#!/usr/bin/env python3
"""Cron Expression Parser — WITHOUT framework. Direct implementation."""
import argparse
import sys
from datetime import datetime, timedelta

def parse_field(s, lo, hi):
    result = set()
    for part in s.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                r = range(lo, hi+1)
            elif "-" in base:
                a, b = base.split("-"); r = range(int(a), int(b)+1)
            else:
                r = range(int(base), hi+1)
            result.update(v for i,v in enumerate(r) if i % step == 0)
        elif "-" in part:
            a, b = part.split("-"); result.update(range(int(a), int(b)+1))
        elif part == "*":
            result.update(range(lo, hi+1))
        else:
            result.add(int(part))
    bad = [v for v in result if v < lo or v > hi]
    if bad: raise ValueError(f"Out of range: {bad} (expected {lo}-{hi})")
    return result

def parse_cron(expr):
    fields = expr.strip().split()
    if len(fields) != 5: raise ValueError(f"Need 5 fields, got {len(fields)}")
    mn = parse_field(fields[0], 0, 59)
    hr = parse_field(fields[1], 0, 23)
    dom = parse_field(fields[2], 1, 31)
    mo = parse_field(fields[3], 1, 12)
    dow = parse_field(fields[4], 0, 6)
    return mn, hr, dom, mo, dow

def next_times(expr, count=5, from_dt=None):
    mn, hr, dom, mo, dow = parse_cron(expr)
    if from_dt is None: from_dt = datetime.now()
    cur = from_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    results = []
    # dow: cron 0=Sun, python weekday() 0=Mon
    for _ in range(527040):  # 1 year in minutes
        # Python weekday: Mon=0,Sun=6 -> cron Sun=0,Sat=6
        cron_dow = (cur.weekday() + 1) % 7
        try:
            if (cur.minute in mn and cur.hour in hr and
                cur.day in dom and cur.month in mo and cron_dow in dow):
                results.append(cur)
                if len(results) >= count: break
        except:
            pass
        cur += timedelta(minutes=1)
    return results

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
n = sub.add_parser("next")
n.add_argument("cron_expr"); n.add_argument("--count", type=int, default=5)
n.add_argument("--from", dest="from_time")
v = sub.add_parser("validate"); v.add_argument("cron_expr")

args = parser.parse_args()

if args.cmd == "next":
    from_dt = None
    if args.from_time:
        from_dt = datetime.strptime(args.from_time, "%Y-%m-%dT%H:%M")
    try:
        times = next_times(args.cron_expr, args.count, from_dt)
        for t in times: print(t.strftime("%Y-%m-%d %H:%M"))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)

elif args.cmd == "validate":
    try:
        mn, hr, dom, mo, dow = parse_cron(args.cron_expr)
        print(f"Valid: '{args.cron_expr}'")
    except ValueError as e:
        print(f"Invalid: {e}", file=sys.stderr); sys.exit(1)
