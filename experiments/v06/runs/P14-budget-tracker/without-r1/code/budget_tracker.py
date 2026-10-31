#!/usr/bin/env python3
"""Budget tracker CLI: monthly budgets per category, expenses in a JSON file."""

import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DEFAULT_DB = "budget_data.json"
WARN_PCT = 80
CENTS = Decimal("0.01")


class BudgetError(Exception):
    pass


def load(path):
    if not os.path.exists(path):
        return {"budgets": {}, "expenses": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise BudgetError(f"{path} is not valid JSON: {e}")
    if not isinstance(data, dict):
        raise BudgetError(f"{path} has unexpected structure")
    data.setdefault("budgets", {})
    data.setdefault("expenses", [])
    return data


def save(path, data):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parse_amount(text):
    try:
        amt = Decimal(str(text).strip())
    except InvalidOperation:
        raise BudgetError(f"invalid amount: {text!r}")
    if not amt.is_finite() or amt <= 0:
        raise BudgetError(f"amount must be a positive number: {text!r}")
    if amt != amt.quantize(CENTS):
        raise BudgetError(f"amount has more than 2 decimal places: {text!r}")
    return amt.quantize(CENTS)


def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise BudgetError(f"invalid date (use YYYY-MM-DD): {text!r}")


def parse_month(text):
    try:
        return datetime.strptime(text, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise BudgetError(f"invalid month (use YYYY-MM): {text!r}")


def norm_cat(name):
    name = name.strip().lower()
    if not name:
        raise BudgetError("category name cannot be empty")
    return name


def alert_for(spent, budget):
    """Return an alert string for the spent/budget level, or None."""
    if budget <= 0:
        return None
    pct = spent / budget * 100
    if pct >= 100:
        return f"ALERT: 100% budget reached ({pct:.0f}%)"
    if pct >= WARN_PCT:
        return f"WARNING: {WARN_PCT}% budget reached ({pct:.0f}%)"
    return None


def month_spent(data, category, month):
    return sum(
        (Decimal(e["amount"]) for e in data["expenses"]
         if e["category"] == category and e["date"].startswith(month)),
        Decimal("0"),
    )


def cmd_set_budget(args, data):
    cat = norm_cat(args.category)
    amt = parse_amount(args.amount)
    data["budgets"][cat] = str(amt)
    print(f"Budget for '{cat}' set to {amt} per month.")
    return True


def cmd_add(args, data):
    cat = norm_cat(args.category)
    if cat not in data["budgets"]:
        known = ", ".join(sorted(data["budgets"])) or "none defined"
        raise BudgetError(f"unknown category '{cat}' (known: {known})")
    amt = parse_amount(args.amount)
    d = parse_date(args.date) if args.date else date.today()
    month = d.strftime("%Y-%m")
    budget = Decimal(data["budgets"][cat])
    before = month_spent(data, cat, month)
    data["expenses"].append(
        {"amount": str(amt), "category": cat, "date": d.isoformat(), "note": args.note or ""}
    )
    after = before + amt
    print(f"Recorded {amt} in '{cat}' on {d.isoformat()}.")
    # Alert on each threshold crossed by this expense.
    for pct, label in ((WARN_PCT, f"{WARN_PCT}%"), (100, "100%")):
        threshold = budget * pct / 100
        if before < threshold <= after:
            print(f"ALERT: '{cat}' reached {label} of its budget for {month} "
                  f"({after} of {budget}).", file=sys.stderr)
    if after > budget and before >= budget:
        print(f"ALERT: '{cat}' is over budget for {month} ({after} of {budget}).",
              file=sys.stderr)
    return True


def cmd_report(args, data):
    month = parse_month(args.month) if args.month else date.today().strftime("%Y-%m")
    if not data["budgets"]:
        print("No budgets defined.")
        return False
    print(f"Spending for {month}")
    print(f"{'Category':<16}{'Spent':>10}{'Budget':>10}{'Left':>10}{'Used':>7}")
    alerts = []
    for cat in sorted(data["budgets"]):
        budget = Decimal(data["budgets"][cat])
        spent = month_spent(data, cat, month)
        pct = spent / budget * 100 if budget else Decimal(0)
        print(f"{cat:<16}{spent:>10.2f}{budget:>10.2f}{budget - spent:>10.2f}{pct:>6.0f}%")
        a = alert_for(spent, budget)
        if a:
            alerts.append(f"  {cat}: {a}")
    if alerts:
        print("\nAlerts:")
        print("\n".join(alerts))
    return False


def cmd_list(args, data):
    month = parse_month(args.month) if args.month else None
    rows = [e for e in data["expenses"] if not month or e["date"].startswith(month)]
    if not rows:
        print("No expenses.")
    for e in sorted(rows, key=lambda e: e["date"]):
        print(f"{e['date']}  {e['category']:<14}{Decimal(e['amount']):>10.2f}  {e['note']}")
    return False


def build_parser():
    p = argparse.ArgumentParser(description="Simple monthly budget tracker.")
    p.add_argument("--file", default=DEFAULT_DB, help=f"JSON data file (default {DEFAULT_DB})")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("set-budget", help="define/update a category's monthly budget")
    s.add_argument("category")
    s.add_argument("amount")
    s.set_defaults(fn=cmd_set_budget)

    s = sub.add_parser("add", help="record an expense")
    s.add_argument("amount")
    s.add_argument("category")
    s.add_argument("--date", help="YYYY-MM-DD (default today)")
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("report", help="spending vs budget for a month")
    s.add_argument("--month", help="YYYY-MM (default current)")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("list", help="list expenses")
    s.add_argument("--month", help="YYYY-MM")
    s.set_defaults(fn=cmd_list)
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
