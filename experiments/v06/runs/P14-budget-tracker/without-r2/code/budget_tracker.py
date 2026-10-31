#!/usr/bin/env python3
"""Budget tracker CLI. Stdlib only.

Usage:
  budget_tracker.py [--file F] set-budget CATEGORY AMOUNT
  budget_tracker.py [--file F] add AMOUNT CATEGORY [--date YYYY-MM-DD] [--note TEXT]
  budget_tracker.py [--file F] report [--month YYYY-MM]
"""
import argparse
import json
import math
import os
import sys
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "budget_data.json"
WARN_PCT = 80
CENTS = Decimal("0.01")


class BudgetError(Exception):
    pass


def parse_amount(text, allow_zero=False):
    try:
        amt = Decimal(str(text).strip())
    except InvalidOperation:
        raise BudgetError(f"invalid amount: {text!r}")
    if not amt.is_finite():
        raise BudgetError(f"invalid amount: {text!r}")
    if amt < 0 or (amt == 0 and not allow_zero):
        raise BudgetError(f"amount must be positive: {text!r}")
    if amt != amt.quantize(CENTS):
        raise BudgetError(f"amount may have at most 2 decimal places: {text!r}")
    return amt.quantize(CENTS)


def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise BudgetError(f"invalid date (expected YYYY-MM-DD): {text!r}")


def load(path):
    if not os.path.exists(path):
        return {"budgets": {}, "expenses": []}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
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


def month_spent(data, category, month):
    total = Decimal("0")
    for e in data["expenses"]:
        if e["category"] == category and e["date"].startswith(month):
            total += Decimal(e["amount"])
    return total


def alert_for(spent, budget):
    """Return an alert string or None."""
    if budget <= 0:
        return "OVER BUDGET (100%)" if spent > 0 else None
    pct = spent / budget * 100
    if pct >= 100:
        return f"ALERT: 100% of budget reached ({pct:.0f}%)"
    if pct >= WARN_PCT:
        return f"WARNING: {WARN_PCT}% of budget reached ({pct:.0f}%)"
    return None


def cmd_set_budget(args, data):
    cat = args.category.strip()
    if not cat:
        raise BudgetError("category must not be empty")
    data["budgets"][cat] = str(parse_amount(args.amount))
    print(f"Budget for '{cat}' set to {data['budgets'][cat]} per month")
    return True


def cmd_add(args, data):
    amount = parse_amount(args.amount)
    cat = args.category.strip()
    if cat not in data["budgets"]:
        known = ", ".join(sorted(data["budgets"])) or "none defined"
        raise BudgetError(f"unknown category {cat!r} (known: {known})")
    d = parse_date(args.date) if args.date else date.today()
    data["expenses"].append(
        {"amount": str(amount), "category": cat, "date": d.isoformat(), "note": args.note}
    )
    print(f"Recorded {amount} in '{cat}' on {d.isoformat()}")
    month = d.strftime("%Y-%m")
    budget = Decimal(data["budgets"][cat])
    msg = alert_for(month_spent(data, cat, month), budget)
    if msg:
        print(f"  {cat} ({month}): {msg}")
    return True


def cmd_report(args, data):
    month = args.month or date.today().strftime("%Y-%m")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise BudgetError(f"invalid month (expected YYYY-MM): {month!r}")
    if not data["budgets"]:
        print("No budgets defined.")
        return False
    print(f"Report for {month}")
    print(f"{'Category':<16}{'Budget':>10}{'Spent':>10}{'Left':>10}{'Used':>7}")
    alerts = []
    for cat in sorted(data["budgets"]):
        budget = Decimal(data["budgets"][cat])
        spent = month_spent(data, cat, month)
        pct = f"{spent / budget * 100:.0f}%" if budget > 0 else "n/a"
        print(f"{cat:<16}{budget:>10}{spent:>10}{budget - spent:>10}{pct:>7}")
        msg = alert_for(spent, budget)
        if msg:
            alerts.append(f"  {cat}: {msg}")
    if alerts:
        print("\nAlerts:")
        print("\n".join(alerts))
    return False


def build_parser():
    p = argparse.ArgumentParser(description="Monthly budget tracker")
    p.add_argument("--file", default=DEFAULT_FILE, help=f"JSON data file (default {DEFAULT_FILE})")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set-budget", help="define/update a monthly budget")
    s.add_argument("category")
    s.add_argument("amount")
    s.set_defaults(fn=cmd_set_budget)
    a = sub.add_parser("add", help="record an expense")
    a.add_argument("amount")
    a.add_argument("category")
    a.add_argument("--date", help="YYYY-MM-DD (default today)")
    a.add_argument("--note", default="")
    a.set_defaults(fn=cmd_add)
    r = sub.add_parser("report", help="spending vs budget")
    r.add_argument("--month", help="YYYY-MM (default current month)")
    r.set_defaults(fn=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        data = load(args.file)
        if args.fn(args, data):
            save(args.file, data)
    except BudgetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
