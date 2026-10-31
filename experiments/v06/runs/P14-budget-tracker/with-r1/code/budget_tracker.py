#!/usr/bin/env python3
"""Budget tracker CLI: monthly budgets per category, expenses in a JSON file."""
import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "budget.json"
WARN_PCT = Decimal(80)
CENT = Decimal("0.01")


class UserError(Exception):
    """Validation or usage error: reported on stderr, exit status 2."""


def parse_amount(text):
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation:
        raise UserError("invalid amount: %r is not a number" % (text,))
    if not value.is_finite():
        raise UserError("invalid amount: %r is not finite" % (text,))
    if value <= 0:
        raise UserError("invalid amount: %s must be greater than zero" % value)
    if value != value.quantize(CENT):
        raise UserError("invalid amount: %s has more than 2 decimal places" % value)
    return value.quantize(CENT)


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (ValueError, TypeError):
        raise UserError("invalid date: %r (expected YYYY-MM-DD)" % (text,))


def parse_month(text):
    try:
        year, month = text.split("-")
        if len(year) != 4 or len(month) != 2:
            raise ValueError
        return date(int(year), int(month), 1).strftime("%Y-%m")
    except ValueError:
        raise UserError("invalid month: %r (expected YYYY-MM)" % (text,))


def load(path):
    if not os.path.exists(path):
        return {"budgets": {}, "expenses": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data.get("budgets"), dict) or not isinstance(data.get("expenses"), list):
            raise ValueError("missing budgets/expenses")
        return data
    except (OSError, ValueError, AttributeError) as exc:
        raise UserError("cannot read %s: %s" % (path, exc))


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def spent_by_category(data, month):
    totals = {}
    for exp in data["expenses"]:
        if exp["date"][:7] == month:
            totals[exp["category"]] = totals.get(exp["category"], Decimal(0)) + Decimal(exp["amount"])
    return totals


def status(spent, budget):
    """Return 'EXCEEDED' (>=100%), 'WARNING' (>=80%) or 'ok'; exact Decimal math."""
    if spent >= budget:
        return "EXCEEDED"
    if spent * 100 >= budget * WARN_PCT:
        return "WARNING"
    return "ok"


def percent(spent, budget):
    return (spent * 100 / budget).quantize(Decimal("0.1"))


def alert_line(category, spent, budget, month):
    st = status(spent, budget)
    if st == "ok":
        return None
    label = "EXCEEDED: reached 100%" if st == "EXCEEDED" else "WARNING: reached 80%"
    return "%s of budget for %s in %s (%s of %s, %s%%)" % (
        label, category, month, spent, budget, percent(spent, budget))


def cmd_set_budget(args):
    amount = parse_amount(args.amount)
    category = args.category.strip()
    if not category:
        raise UserError("category must not be empty")
    data = load(args.file)
    data["budgets"][category] = str(amount)
    save(args.file, data)
    print("Budget for %s set to %s per month" % (category, amount))


def cmd_add(args):
    amount = parse_amount(args.amount)
    when = parse_date(args.date) if args.date else date.today()
    data = load(args.file)
    if args.category not in data["budgets"]:
        raise UserError("unknown category: %s (set a budget first)" % args.category)
    data["expenses"].append({
        "amount": str(amount),
        "category": args.category,
        "date": when.isoformat(),
        "note": args.note or "",
    })
    save(args.file, data)
    print("Recorded %s in %s on %s" % (amount, args.category, when.isoformat()))
    month = when.strftime("%Y-%m")
    spent = spent_by_category(data, month).get(args.category, Decimal(0))
    line = alert_line(args.category, spent, Decimal(data["budgets"][args.category]), month)
    if line:
        print(line)


def cmd_report(args):
    month = parse_month(args.month) if args.month else date.today().strftime("%Y-%m")
    data = load(args.file)
    totals = spent_by_category(data, month)
    print("Report for %s" % month)
    print("%-20s %12s %12s %8s  %s" % ("category", "spent", "budget", "percent", "status"))
    alerts = []
    for category in sorted(data["budgets"]):
        budget = Decimal(data["budgets"][category])
        spent = totals.get(category, Decimal(0))
        print("%-20s %12s %12s %7s%%  %s" % (
            category, spent, budget, percent(spent, budget), status(spent, budget)))
        line = alert_line(category, spent, budget, month)
        if line:
            alerts.append(line)
    for line in alerts:
        print(line)


def build_parser():
    parser = argparse.ArgumentParser(prog="budget_tracker", description="Monthly budget tracker")
    parser.add_argument("--file", default=DEFAULT_FILE, help="JSON data file (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("set-budget", help="set the monthly budget of a category")
    p.add_argument("category")
    p.add_argument("amount")
    p.set_defaults(func=cmd_set_budget)
    p = sub.add_parser("add", help="record an expense")
    p.add_argument("amount")
    p.add_argument("category")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_add)
    p = sub.add_parser("report", help="spending per category against budget")
    p.add_argument("--month", help="YYYY-MM (default: current month)")
    p.set_defaults(func=cmd_report)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except UserError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
