#!/usr/bin/env python3
"""Budget tracker CLI: monthly budgets per category, expenses in a JSON file.

Usage:
  budget_tracker.py set-budget CATEGORY AMOUNT
  budget_tracker.py add AMOUNT CATEGORY [--date YYYY-MM-DD] [--note TEXT]
  budget_tracker.py report [--month YYYY-MM]
  budget_tracker.py --file data.json ...   (default: budget_data.json)
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "budget_data.json"
WARN_PCT = Decimal("80")
FULL_PCT = Decimal("100")


class BudgetError(Exception):
    pass


def parse_amount(text):
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation:
        raise BudgetError(f"invalid amount: {text!r}")
    if not value.is_finite() or value <= 0:
        raise BudgetError(f"amount must be a positive number: {text!r}")
    if value.as_tuple().exponent < -2:
        raise BudgetError(f"amount has more than 2 decimal places: {text!r}")
    return value.quantize(Decimal("0.01"))


def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise BudgetError(f"invalid date (expected YYYY-MM-DD): {text!r}")


def parse_month(text):
    try:
        return datetime.strptime(text, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise BudgetError(f"invalid month (expected YYYY-MM): {text!r}")


def load(path):
    if not os.path.exists(path):
        return {"budgets": {}, "expenses": []}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise BudgetError(f"cannot read {path}: {e}")
    if not isinstance(data, dict):
        raise BudgetError(f"{path}: unexpected format")
    data.setdefault("budgets", {})
    data.setdefault("expenses", [])
    return data


def save(path, data):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def norm_cat(name):
    name = name.strip().lower()
    if not name:
        raise BudgetError("category must not be empty")
    return name


def alert_for(spent, budget):
    """Return an alert string for spent/budget, or None."""
    pct = spent / budget * 100
    if pct >= FULL_PCT:
        return f"ALERT: reached 100% of budget ({pct:.0f}%)"
    if pct >= WARN_PCT:
        return f"WARNING: reached 80% of budget ({pct:.0f}%)"
    return None


def month_spend(data, month):
    totals = {}
    for e in data["expenses"]:
        if e["date"].startswith(month):
            totals[e["category"]] = totals.get(e["category"], Decimal(0)) + Decimal(e["amount"])
    return totals


def cmd_set_budget(args, data):
    cat = norm_cat(args.category)
    amount = parse_amount(args.amount)
    data["budgets"][cat] = str(amount)
    save(args.file, data)
    print(f"Budget for {cat}: {amount:.2f} per month")


def cmd_add(args, data):
    amount = parse_amount(args.amount)
    cat = norm_cat(args.category)
    if cat not in data["budgets"]:
        known = ", ".join(sorted(data["budgets"])) or "none defined"
        raise BudgetError(f"unknown category {cat!r} (known: {known})")
    when = parse_date(args.date) if args.date else date.today()
    data["expenses"].append(
        {"amount": str(amount), "category": cat, "date": when.isoformat(), "note": args.note or ""}
    )
    save(args.file, data)
    print(f"Recorded {amount:.2f} in {cat} on {when.isoformat()}")
    month = when.strftime("%Y-%m")
    spent = month_spend(data, month).get(cat, Decimal(0))
    budget = Decimal(data["budgets"][cat])
    msg = alert_for(spent, budget)
    if msg:
        print(f"{cat} ({month}): {spent:.2f} / {budget:.2f} - {msg}")


def cmd_report(args, data):
    month = parse_month(args.month) if args.month else date.today().strftime("%Y-%m")
    spent = month_spend(data, month)
    print(f"Budget report for {month}")
    if not data["budgets"]:
        print("No budgets defined.")
        return
    print(f"{'Category':<16}{'Spent':>10}{'Budget':>10}{'Left':>10}{'Used':>7}")
    for cat in sorted(data["budgets"]):
        budget = Decimal(data["budgets"][cat])
        s = spent.get(cat, Decimal(0))
        pct = s / budget * 100
        print(f"{cat:<16}{s:>10.2f}{budget:>10.2f}{budget - s:>10.2f}{pct:>6.0f}%")
        msg = alert_for(s, budget)
        if msg:
            print(f"  {msg}")
    for cat in sorted(set(spent) - set(data["budgets"])):
        print(f"{cat:<16}{spent[cat]:>10.2f}  (no budget)")


def build_parser():
    p = argparse.ArgumentParser(description="Monthly budget tracker")
    p.add_argument("--file", default=DEFAULT_FILE, help=f"JSON data file (default {DEFAULT_FILE})")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set-budget", help="define/update a category's monthly budget")
    s.add_argument("category")
    s.add_argument("amount")
    s.set_defaults(fn=cmd_set_budget)
    a = sub.add_parser("add", help="record an expense")
    a.add_argument("amount")
    a.add_argument("category")
    a.add_argument("--date", help="YYYY-MM-DD (default today)")
    a.add_argument("--note", help="free-text note")
    a.set_defaults(fn=cmd_add)
    r = sub.add_parser("report", help="spending vs budget for a month")
    r.add_argument("--month", help="YYYY-MM (default current month)")
    r.set_defaults(fn=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.fn(args, load(args.file))
    except BudgetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
