#!/usr/bin/env python3
"""CLI expense splitter: record shared expenses, show balances, plan settlements.

Amounts are stored as integer cents to avoid floating-point drift.

Usage:
    expense_splitter.py add --payer Alice --amount 60 --desc Dinner --with Alice Bob Carol
    expense_splitter.py list
    expense_splitter.py balances
    expense_splitter.py settle
    expense_splitter.py remove 2
"""

import argparse
import heapq
import json
import os
import sys
import tempfile
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "expenses.json"


# ---------- money helpers ----------

def parse_cents(text):
    """Parse a positive decimal string with at most 2 decimals into cents."""
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}")
    if not d.is_finite() or d <= 0:
        raise ValueError("amount must be a positive number")
    cents = d * 100
    if cents != cents.to_integral_value():
        raise ValueError("amount can have at most 2 decimal places")
    return int(cents)


def fmt(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


# ---------- storage ----------

def load(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        expenses = data["expenses"]
        for e in expenses:
            if not (isinstance(e["payer"], str) and isinstance(e["amount_cents"], int)
                    and e["participants"]):
                raise ValueError
        return expenses
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        sys.exit(f"error: {path} is not a valid expense file")


def save(path, expenses):
    # Write atomically so a crash can't leave a truncated file.
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"expenses": expenses}, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


# ---------- core logic ----------

def split_equally(amount_cents, participants):
    """Return {person: share}; leftover cents go to the first participants."""
    base, extra = divmod(amount_cents, len(participants))
    return {p: base + (1 if i < extra else 0) for i, p in enumerate(participants)}


def compute_balances(expenses):
    """Positive balance = is owed money; negative = owes money."""
    bal = {}
    for e in expenses:
        bal[e["payer"]] = bal.get(e["payer"], 0) + e["amount_cents"]
        for p, share in split_equally(e["amount_cents"], e["participants"]).items():
            bal[p] = bal.get(p, 0) - share
    return bal


def settlement_plan(balances):
    """Greedy: repeatedly match the largest debtor with the largest creditor.

    Each transfer fully settles at least one person, so there are at most
    (n - 1) transfers. Returns a list of (debtor, creditor, cents).
    """
    creditors = [(-b, p) for p, b in balances.items() if b > 0]
    debtors = [(b, p) for p, b in balances.items() if b < 0]  # b is negative
    heapq.heapify(creditors)  # min-heap on negated amount => largest first
    heapq.heapify(debtors)    # most negative first => largest debt first
    plan = []
    while creditors and debtors:
        neg_c, cred = heapq.heappop(creditors)
        neg_d, debt = heapq.heappop(debtors)
        credit, owed = -neg_c, -neg_d
        amt = min(credit, owed)
        plan.append((debt, cred, amt))
        if credit > amt:
            heapq.heappush(creditors, (-(credit - amt), cred))
        if owed > amt:
            heapq.heappush(debtors, (-(owed - amt), debt))
    return plan


# ---------- commands ----------

def cmd_add(args):
    try:
        cents = parse_cents(args.amount)
    except ValueError as err:
        sys.exit(f"error: {err}")
    payer = args.payer.strip()
    # Dedupe participants, keeping order.
    people = list(dict.fromkeys(p.strip() for p in args.with_))
    if not payer or not all(people):
        sys.exit("error: names must not be empty")
    expenses = load(args.file)
    expenses.append({
        "payer": payer,
        "amount_cents": cents,
        "description": args.desc,
        "participants": people,
    })
    save(args.file, expenses)
    share = fmt(cents // len(people))
    print(f"Added #{len(expenses)}: {payer} paid {fmt(cents)} for {args.desc!r}, "
          f"split among {', '.join(people)} (~{share} each)")


def cmd_list(args):
    expenses = load(args.file)
    if not expenses:
        print("No expenses recorded.")
        return
    for i, e in enumerate(expenses, 1):
        print(f"{i}. {e['description']}: {e['payer']} paid {fmt(e['amount_cents'])} "
              f"for {', '.join(e['participants'])}")


def cmd_remove(args):
    expenses = load(args.file)
    if not 1 <= args.number <= len(expenses):
        sys.exit(f"error: no expense #{args.number}")
    e = expenses.pop(args.number - 1)
    save(args.file, expenses)
    print(f"Removed #{args.number}: {e['description']}")


def cmd_balances(args):
    bal = compute_balances(load(args.file))
    if not bal:
        print("No expenses recorded.")
        return
    width = max(len(p) for p in bal)
    for p, b in sorted(bal.items()):
        note = "is owed" if b > 0 else "owes" if b < 0 else "settled"
        print(f"{p:<{width}}  {fmt(b):>10}  ({note})")


def cmd_settle(args):
    plan = settlement_plan(compute_balances(load(args.file)))
    if not plan:
        print("Everyone is settled up.")
        return
    for debtor, creditor, cents in plan:
        print(f"{debtor} pays {creditor} {fmt(cents)}")
    print(f"({len(plan)} transfer{'s' if len(plan) != 1 else ''})")


def build_parser():
    ap = argparse.ArgumentParser(description="Split group expenses equally.")
    ap.add_argument("-f", "--file", default=DEFAULT_FILE,
                    help=f"JSON data file (default: {DEFAULT_FILE})")
    sub = ap.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="record an expense")
    add.add_argument("--payer", required=True)
    add.add_argument("--amount", required=True, help="e.g. 42.50")
    add.add_argument("--desc", required=True, help="description")
    add.add_argument("--with", dest="with_", nargs="+", required=True,
                     metavar="PERSON", help="participants (include the payer if they share)")
    add.set_defaults(func=cmd_add)

    sub.add_parser("list", help="list expenses").set_defaults(func=cmd_list)
    rm = sub.add_parser("remove", help="remove an expense by number")
    rm.add_argument("number", type=int)
    rm.set_defaults(func=cmd_remove)
    sub.add_parser("balances", help="show each person's balance").set_defaults(func=cmd_balances)
    sub.add_parser("settle", help="show a settlement plan").set_defaults(func=cmd_settle)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
