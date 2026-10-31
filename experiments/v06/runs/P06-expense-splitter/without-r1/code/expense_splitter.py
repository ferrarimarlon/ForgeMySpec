#!/usr/bin/env python3
"""Expense splitter CLI.

Records group expenses (split equally among participants), stores them in a
JSON file, shows balances, and computes a settlement plan using a greedy
algorithm (repeatedly match the largest debtor with the largest creditor).

Usage:
    expense_splitter.py add --payer Alice --amount 30.00 \
        --description Dinner --participants Alice Bob Carol
    expense_splitter.py list
    expense_splitter.py balances
    expense_splitter.py settle

Amounts are handled as integer cents internally to avoid float errors.
"""

import argparse
import heapq
import json
import os
import sys
import tempfile
from decimal import Decimal, InvalidOperation

DEFAULT_FILE = "expenses.json"


def parse_cents(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}")
    if not value.is_finite() or value <= 0:
        raise ValueError("amount must be a positive number")
    cents = value * 100
    if cents != cents.to_integral_value():
        raise ValueError("amount cannot have more than 2 decimal places")
    return int(cents)


def fmt(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def load(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is not valid JSON: {e}")
    if not isinstance(data, list):
        raise ValueError(f"{path} has unexpected format")
    return data


def save(path, expenses):
    # Write atomically so a crash can't corrupt the existing data.
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(expenses, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def shares(expense):
    """Split amount equally; leftover cents go to the first participants."""
    people = expense["participants"]
    base, extra = divmod(expense["amount_cents"], len(people))
    return {p: base + (1 if i < extra else 0) for i, p in enumerate(people)}


def compute_balances(expenses):
    """Positive = is owed money; negative = owes money."""
    bal = {}
    for e in expenses:
        bal[e["payer"]] = bal.get(e["payer"], 0) + e["amount_cents"]
        for person, share in shares(e).items():
            bal[person] = bal.get(person, 0) - share
    return bal


def settle_plan(balances):
    """Greedy: largest debtor pays largest creditor until all are settled."""
    creditors = [(-b, p) for p, b in balances.items() if b > 0]
    debtors = [(b, p) for p, b in balances.items() if b < 0]
    heapq.heapify(creditors)
    heapq.heapify(debtors)
    transfers = []
    while creditors and debtors:
        neg_credit, creditor = heapq.heappop(creditors)
        neg_debt, debtor = heapq.heappop(debtors)
        credit, debt = -neg_credit, -neg_debt
        amount = min(credit, debt)
        transfers.append((debtor, creditor, amount))
        if credit > amount:
            heapq.heappush(creditors, (-(credit - amount), creditor))
        if debt > amount:
            heapq.heappush(debtors, (-(debt - amount), debtor))
    return transfers


def cmd_add(args):
    amount = parse_cents(args.amount)
    payer = args.payer.strip()
    participants = []
    for p in args.participants:
        p = p.strip()
        if p and p not in participants:
            participants.append(p)
    if not payer:
        raise ValueError("payer must not be empty")
    if not participants:
        raise ValueError("at least one participant is required")
    expenses = load(args.file)
    expenses.append({
        "payer": payer,
        "amount_cents": amount,
        "description": args.description,
        "participants": participants,
    })
    save(args.file, expenses)
    print(f"Added: {payer} paid {fmt(amount)} for {args.description!r} "
          f"split among {', '.join(participants)}")


def cmd_list(args):
    expenses = load(args.file)
    if not expenses:
        print("No expenses recorded.")
        return
    for i, e in enumerate(expenses, 1):
        print(f"{i}. {e['description']}: {e['payer']} paid "
              f"{fmt(e['amount_cents'])} for {', '.join(e['participants'])}")


def cmd_balances(args):
    bal = compute_balances(load(args.file))
    if not bal:
        print("No expenses recorded.")
        return
    width = max(len(p) for p in bal)
    for person in sorted(bal):
        b = bal[person]
        note = "is owed" if b > 0 else "owes" if b < 0 else "settled"
        print(f"{person:<{width}}  {fmt(b):>10}  ({note})")


def cmd_settle(args):
    transfers = settle_plan(compute_balances(load(args.file)))
    if not transfers:
        print("Everyone is settled up.")
        return
    for debtor, creditor, amount in transfers:
        print(f"{debtor} pays {creditor} {fmt(amount)}")
    print(f"{len(transfers)} transfer(s) needed.")


def build_parser():
    parser = argparse.ArgumentParser(description="Group expense splitter")
    parser.add_argument("-f", "--file", default=DEFAULT_FILE,
                        help=f"JSON data file (default: {DEFAULT_FILE})")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="record an expense")
    add.add_argument("--payer", required=True)
    add.add_argument("--amount", required=True, help="e.g. 42.50")
    add.add_argument("--description", required=True)
    add.add_argument("--participants", required=True, nargs="+",
                     help="people sharing the expense equally")
    add.set_defaults(func=cmd_add)

    sub.add_parser("list", help="list expenses").set_defaults(func=cmd_list)
    sub.add_parser("balances", help="show each person's balance"
                   ).set_defaults(func=cmd_balances)
    sub.add_parser("settle", help="show a minimal settlement plan"
                   ).set_defaults(func=cmd_settle)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
