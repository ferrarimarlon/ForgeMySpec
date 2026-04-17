#!/usr/bin/env python3
"""Expense Splitter CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: greedy settlement, fractional cents rounded to 2dp.
"""
import argparse
import json
import os
import sys
from typing import Dict, List

DATA_FILE = "expenses.json"


def load_data(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"expenses": []}


def save_data(data: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def compute_balances(expenses: List[dict]) -> Dict[str, float]:
    """Net balance per person. Positive = owed money. Negative = owes money."""
    balances: Dict[str, float] = {}
    for exp in expenses:
        payer = exp["payer"]
        amount = exp["amount"]
        participants = exp["participants"]
        n = len(participants)
        if n == 0:
            continue
        share = round(amount / n, 2)
        # Payer receives back: total minus their own share
        payer_share = share
        balances[payer] = balances.get(payer, 0.0) + amount - payer_share
        for p in participants:
            if p == payer:
                continue
            balances[p] = balances.get(p, 0.0) - share
        # Fix rounding: adjust payer's balance so sum stays at zero
        # Recompute total distributed
    return {k: round(v, 2) for k, v in balances.items()}


def greedy_settle(balances: Dict[str, float]) -> List[dict]:
    """Greedy: match largest creditor with largest debtor."""
    # creditors: positive balance (owed money)
    # debtors: negative balance (owes money)
    creditors = sorted(
        [(name, bal) for name, bal in balances.items() if bal > 0.001],
        key=lambda x: -x[1],
    )
    debtors = sorted(
        [(name, -bal) for name, bal in balances.items() if bal < -0.001],
        key=lambda x: -x[1],
    )
    transactions = []
    ci, di = 0, 0
    cred = list(creditors)
    debt = list(debtors)
    while ci < len(cred) and di < len(debt):
        creditor, c_amt = cred[ci]
        debtor, d_amt = debt[di]
        settled = min(c_amt, d_amt)
        settled = round(settled, 2)
        transactions.append({
            "from": debtor,
            "to": creditor,
            "amount": settled,
        })
        c_amt = round(c_amt - settled, 2)
        d_amt = round(d_amt - settled, 2)
        if c_amt < 0.001:
            ci += 1
        else:
            cred[ci] = (creditor, c_amt)
        if d_amt < 0.001:
            di += 1
        else:
            debt[di] = (debtor, d_amt)
    return transactions


def cmd_add(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    participants = [p.strip() for p in args.for_whom.split(",")]
    expense_id = len(data["expenses"]) + 1
    expense = {
        "id": expense_id,
        "payer": args.payer,
        "amount": round(float(args.amount), 2),
        "participants": participants,
        "description": args.description or "",
    }
    data["expenses"].append(expense)
    save_data(data, args.file)
    print(f"Added expense #{expense_id}: {args.payer} paid ${expense['amount']:.2f} for {', '.join(participants)}")


def cmd_balances(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    if not data["expenses"]:
        print("No expenses recorded.")
        return
    balances = compute_balances(data["expenses"])
    print("Balances:")
    for person, bal in sorted(balances.items()):
        if bal > 0:
            print(f"  {person}: +${bal:.2f} (is owed)")
        elif bal < 0:
            print(f"  {person}: -${abs(bal):.2f} (owes)")
        else:
            print(f"  {person}: $0.00 (settled)")


def cmd_settle(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    if not data["expenses"]:
        print("No expenses to settle.")
        return
    balances = compute_balances(data["expenses"])
    transactions = greedy_settle(balances)
    if not transactions:
        print("All settled! No transactions needed.")
        return
    print(f"Settlement plan ({len(transactions)} transaction(s)):")
    for i, t in enumerate(transactions, 1):
        print(f"  {i}. {t['from']} pays {t['to']} ${t['amount']:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Expense Splitter CLI")
    parser.add_argument("--file", default=DATA_FILE, help="Data file path")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add an expense")
    p_add.add_argument("payer", help="Who paid")
    p_add.add_argument("amount", help="Amount paid")
    p_add.add_argument("--for", dest="for_whom", required=True,
                       help="Comma-separated list of participants (including payer if applicable)")
    p_add.add_argument("--description", "-d", default="", help="Description")

    sub.add_parser("balances", help="Show balances")
    sub.add_parser("settle", help="Show settlement transactions")

    args = parser.parse_args()
    if args.command == "add":
        cmd_add(args)
    elif args.command == "balances":
        cmd_balances(args)
    elif args.command == "settle":
        cmd_settle(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
