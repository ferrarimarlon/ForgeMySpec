#!/usr/bin/env python3
"""Expense splitter CLI: add expenses, show balances, compute a settlement plan.

Money is stored as integer cents. Data lives in a JSON file (default expenses.json).
"""
import argparse
import json
import os
import sys
import tempfile
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "expenses.json"


class SplitterError(Exception):
    pass


def parse_amount(text):
    """Parse a positive decimal with at most 2 places into integer cents."""
    try:
        d = Decimal(str(text).strip())
    except InvalidOperation:
        raise SplitterError("invalid amount: %r" % (text,))
    if not d.is_finite() or d <= 0:
        raise SplitterError("amount must be a positive number: %r" % (text,))
    cents = d * 100
    if cents != cents.to_integral_value():
        raise SplitterError("amount has more than 2 decimal places: %r" % (text,))
    return int(cents)


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def split_equally(cents, participants):
    """Shares differ by at most one cent and sum exactly to cents."""
    n = len(participants)
    base, rem = divmod(cents, n)
    return {p: base + (1 if i < rem else 0) for i, p in enumerate(participants)}


def load(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise SplitterError("cannot read %s: %s" % (path, e))
    if not isinstance(data, dict) or not isinstance(data.get("expenses"), list):
        raise SplitterError("%s is not a valid expense file" % path)
    for e in data["expenses"]:
        ok = (
            isinstance(e, dict)
            and isinstance(e.get("payer"), str)
            and isinstance(e.get("amount_cents"), int)
            and not isinstance(e.get("amount_cents"), bool)
            and e["amount_cents"] > 0
            and isinstance(e.get("description"), str)
            and isinstance(e.get("participants"), list)
            and e["participants"]
            and all(isinstance(p, str) for p in e["participants"])
            and len(set(e["participants"])) == len(e["participants"])
        )
        if not ok:
            raise SplitterError("%s contains a malformed expense" % path)
    return data["expenses"]


def save(path, expenses):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".expenses-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"expenses": expenses}, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def make_expense(payer, amount, description, participants):
    payer = (payer or "").strip()
    if not payer:
        raise SplitterError("payer must not be empty")
    names = [p.strip() for p in participants]
    if not names or any(not p for p in names):
        raise SplitterError("participants must be a non-empty list of names")
    if len(set(names)) != len(names):
        raise SplitterError("participants must be unique")
    return {
        "payer": payer,
        "amount_cents": parse_amount(amount),
        "description": description,
        "participants": names,
    }


def compute_balances(expenses):
    """Net balance per person in cents: paid minus owed. Sums to zero."""
    bal = {}
    for e in expenses:
        bal[e["payer"]] = bal.get(e["payer"], 0) + e["amount_cents"]
        for p, share in split_equally(e["amount_cents"], e["participants"]).items():
            bal[p] = bal.get(p, 0) - share
    return bal


def settle(balances):
    """Greedy plan: repeatedly transfer from the largest debtor to the largest creditor."""
    debtors = {p: -b for p, b in balances.items() if b < 0}
    creditors = {p: b for p, b in balances.items() if b > 0}
    transfers = []
    while debtors and creditors:
        d = min(debtors, key=lambda p: (-debtors[p], p))
        c = min(creditors, key=lambda p: (-creditors[p], p))
        amt = min(debtors[d], creditors[c])
        transfers.append((d, c, amt))
        debtors[d] -= amt
        creditors[c] -= amt
        if debtors[d] == 0:
            del debtors[d]
        if creditors[c] == 0:
            del creditors[c]
    return transfers


def build_parser():
    ap = argparse.ArgumentParser(description="Split group expenses equally.")
    ap.add_argument("--file", default=DEFAULT_FILE, help="JSON data file (default %(default)s)")
    sub = ap.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="record an expense")
    add.add_argument("--payer", required=True)
    add.add_argument("--amount", required=True)
    add.add_argument("--description", default="")
    add.add_argument("--participants", required=True, nargs="+",
                     help="names (space- or comma-separated)")
    sub.add_parser("balances", help="show each person's balance")
    sub.add_parser("settle", help="show a settlement plan")
    return ap


def run(args, out):
    if args.command == "add":
        names = [n for chunk in args.participants for n in chunk.split(",")]
        expenses = load(args.file)
        expenses.append(make_expense(args.payer, args.amount, args.description, names))
        save(args.file, expenses)
        e = expenses[-1]
        print("Recorded: %s paid %s for %s (%d participants)"
              % (e["payer"], format_cents(e["amount_cents"]), e["description"] or "-",
                 len(e["participants"])), file=out)
    elif args.command == "balances":
        bal = compute_balances(load(args.file))
        for p in sorted(bal):
            print("%s: %s" % (p, format_cents(bal[p])), file=out)
    elif args.command == "settle":
        plan = settle(compute_balances(load(args.file)))
        if not plan:
            print("All settled.", file=out)
        for d, c, amt in plan:
            print("%s pays %s %s" % (d, c, format_cents(amt)), file=out)


def main(argv=None, out=None):
    out = out or sys.stdout
    try:
        args = build_parser().parse_args(argv)
        run(args, out)
    except SplitterError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
