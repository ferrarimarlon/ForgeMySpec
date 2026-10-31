#!/usr/bin/env python3
"""Budget tracker CLI: monthly budgets per category, expenses in a JSON file."""
import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "budget" + ".json"
WARN_PCT = 80
EXCEEDED_PCT = 100


class TrackerError(Exception):
    pass


def parse_amount(text):
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        raise TrackerError("invalid amount: %r" % (text,))
    if not value.is_finite() or value <= 0:
        raise TrackerError("invalid amount: %r (must be positive and finite)" % (text,))
    if value != value.quantize(Decimal("0.01")):
        raise TrackerError("invalid amount: %r (at most 2 decimals)" % (text,))
    return value.quantize(Decimal("0.01"))


def parse_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except (ValueError, TypeError):
        raise TrackerError("invalid date: %r (use YYYY-MM-DD)" % (text,))


def parse_month(text):
    try:
        year, month = text.split("-")
        if len(year) != 4 or len(month) != 2:
            raise ValueError
        date(int(year), int(month), 1)
    except (ValueError, AttributeError):
        raise TrackerError("invalid month: %r (use YYYY-MM)" % (text,))
    return text


def load(path):
    if not os.path.exists(path):
        return {"budgets": {}, "expenses": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data.get("budgets"), dict) or not isinstance(data.get("expenses"), list):
            raise ValueError("missing budgets/expenses")
    except (ValueError, AttributeError, OSError) as exc:
        raise TrackerError("cannot read data file %s: %s" % (path, exc))
    return data


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def budget_for(data, category, month):
    value = data["budgets"].get(month, {}).get(category)
    return Decimal(value) if value is not None else None


def spent(data, category, month):
    total = Decimal("0.00")
    for e in data["expenses"]:
        if e["category"] == category and e["date"].startswith(month):
            total += Decimal(e["amount"])
    return total


def alert_level(spent_amount, budget):
    """Return None, 'warning' (>=80%) or 'exceeded' (>=100%)."""
    if budget is None or budget <= 0:
        return None
    if spent_amount * 100 >= budget * EXCEEDED_PCT:
        return "exceeded"
    if spent_amount * 100 >= budget * WARN_PCT:
        return "warning"
    return None


def alert_text(category, month, spent_amount, budget):
    level = alert_level(spent_amount, budget)
    if level is None:
        return None
    pct = spent_amount * 100 / budget
    if level == "exceeded":
        return "ALERT: %s %s exceeded budget (100%%): %s of %s (%.1f%%)" % (
            category, month, spent_amount, budget, pct)
    return "ALERT: %s %s reached 80%% of budget: %s of %s (%.1f%%)" % (
        category, month, spent_amount, budget, pct)


def cmd_set_budget(args, out):
    month = parse_month(args.month)
    amount = parse_amount(args.amount)
    category = args.category.strip()
    if not category:
        raise TrackerError("category must not be empty")
    data = load(args.file)
    data["budgets"].setdefault(month, {})[category] = str(amount)
    save(args.file, data)
    print("Budget %s %s = %s" % (month, category, amount), file=out)


def cmd_add(args, out):
    amount = parse_amount(args.amount)
    day = parse_date(args.date)
    month = day[:7]
    data = load(args.file)
    known = {c for cats in data["budgets"].values() for c in cats}
    if args.category not in known:
        raise TrackerError("unknown category: %r" % args.category)
    data["expenses"].append({"amount": str(amount), "category": args.category,
                             "date": day, "note": args.note or ""})
    save(args.file, data)
    print("Recorded %s %s on %s" % (amount, args.category, day), file=out)
    text = alert_text(args.category, month, spent(data, args.category, month),
                      budget_for(data, args.category, month))
    if text:
        print(text, file=out)


def cmd_report(args, out):
    month = parse_month(args.month) if args.month else date.today().strftime("%Y-%m")
    data = load(args.file)
    cats = set(data["budgets"].get(month, {}))
    cats |= {e["category"] for e in data["expenses"] if e["date"].startswith(month)}
    print("Report %s" % month, file=out)
    alerts = []
    for cat in sorted(cats):
        s = spent(data, cat, month)
        b = budget_for(data, cat, month)
        if b is None or b <= 0:
            print("%-15s spent %10s  budget %10s  %6s" % (cat, s, "-", "-"), file=out)
            continue
        print("%-15s spent %10s  budget %10s  %5.1f%%" % (cat, s, b, s * 100 / b), file=out)
        text = alert_text(cat, month, s, b)
        if text:
            alerts.append(text)
    for a in alerts:
        print(a, file=out)


def build_parser():
    p = argparse.ArgumentParser(prog="budget_tracker")
    p.add_argument("--file", default=DEFAULT_FILE, help="JSON data file")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("set-budget", help="define a monthly budget for a category")
    s.add_argument("month", help="YYYY-MM")
    s.add_argument("category")
    s.add_argument("amount")
    s.set_defaults(func=cmd_set_budget)
    a = sub.add_parser("add", help="record an expense")
    a.add_argument("amount")
    a.add_argument("category")
    a.add_argument("date", help="YYYY-MM-DD")
    a.add_argument("note", nargs="?", default="")
    a.set_defaults(func=cmd_add)
    r = sub.add_parser("report", help="spending vs budget for a month")
    r.add_argument("month", nargs="?", help="YYYY-MM (default: current)")
    r.set_defaults(func=cmd_report)
    return p


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    try:
        args.func(args, out)
    except TrackerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
