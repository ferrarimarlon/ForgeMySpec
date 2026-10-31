#!/usr/bin/env python3
"""Budget tracker CLI: monthly budgets per category, expenses in a JSON file."""
import argparse
import datetime
import json
import os
import sys
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "budget_data" + ".json"
WARN_PCT = Decimal(80)
OVER_PCT = Decimal(100)


class TrackerError(Exception):
    pass


def parse_amount(text):
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        raise TrackerError("invalid amount: %r" % (text,))
    if not value.is_finite() or value <= 0:
        raise TrackerError("invalid amount: %r (must be a positive number)" % (text,))
    if value != value.quantize(Decimal("0.01")):
        raise TrackerError("invalid amount: %r (at most 2 decimal places)" % (text,))
    return value.quantize(Decimal("0.01"))


def parse_date(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise TrackerError("invalid date: %r (expected YYYY-MM-DD)" % (text,))


def parse_month(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m").strftime("%Y-%m")
    except (ValueError, TypeError):
        raise TrackerError("invalid month: %r (expected YYYY-MM)" % (text,))


def load(path):
    if not os.path.exists(path):
        return {"budgets": {}, "expenses": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data.get("budgets"), dict) or not isinstance(data.get("expenses"), list):
            raise ValueError("bad structure")
    except (ValueError, AttributeError, OSError) as exc:
        raise TrackerError("cannot read data file %s: %s" % (path, exc))
    return data


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def cmd_set_budget(args):
    category = args.category.strip()
    if not category:
        raise TrackerError("category must not be empty")
    amount = parse_amount(args.amount)
    data = load(args.file)
    data["budgets"][category] = str(amount)
    save(args.file, data)
    print("Budget for %s set to %s per month" % (category, amount))


def alert_for(spent, budget):
    pct = spent * 100 / budget
    if pct >= OVER_PCT:
        return pct, "ALERT: over budget (%.1f%% of budget used)" % pct
    if pct >= WARN_PCT:
        return pct, "WARNING: %.1f%% of budget used (80%% threshold reached)" % pct
    return pct, None


def month_spent(data, category, month):
    total = Decimal(0)
    for e in data["expenses"]:
        if e["category"] == category and e["date"].startswith(month):
            total += Decimal(e["amount"])
    return total


def cmd_add(args):
    amount = parse_amount(args.amount)
    date = parse_date(args.date)
    data = load(args.file)
    if args.category not in data["budgets"]:
        raise TrackerError("unknown category: %r (set a budget first)" % args.category)
    data["expenses"].append({
        "amount": str(amount), "category": args.category,
        "date": date.isoformat(), "note": args.note or "",
    })
    save(args.file, data)
    print("Recorded %s in %s on %s" % (amount, args.category, date.isoformat()))
    month = date.strftime("%Y-%m")
    budget = Decimal(data["budgets"][args.category])
    _, msg = alert_for(month_spent(data, args.category, month), budget)
    if msg:
        print("%s [%s %s]" % (msg, args.category, month))


def cmd_report(args):
    month = parse_month(args.month) if args.month else datetime.date.today().strftime("%Y-%m")
    data = load(args.file)
    print("Report for %s" % month)
    print("%-16s %10s %10s %8s" % ("category", "spent", "budget", "used"))
    alerts = []
    for category in sorted(data["budgets"]):
        budget = Decimal(data["budgets"][category])
        spent = month_spent(data, category, month)
        pct, msg = alert_for(spent, budget)
        print("%-16s %10s %10s %7.1f%%" % (category, spent, budget, pct))
        if msg:
            alerts.append("%s: %s" % (category, msg))
    for line in alerts:
        print(line)


def build_parser():
    p = argparse.ArgumentParser(description="Monthly budget tracker")
    p.add_argument("--file", default=DEFAULT_FILE, help="JSON data file")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("set-budget", help="set monthly budget for a category")
    s.add_argument("category")
    s.add_argument("amount")
    s.set_defaults(func=cmd_set_budget)
    a = sub.add_parser("add", help="record an expense")
    a.add_argument("amount")
    a.add_argument("category")
    a.add_argument("--date", default=datetime.date.today().isoformat())
    a.add_argument("--note", default="")
    a.set_defaults(func=cmd_add)
    r = sub.add_parser("report", help="spending vs budget")
    r.add_argument("--month", help="YYYY-MM (default: current month)")
    r.set_defaults(func=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except TrackerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
