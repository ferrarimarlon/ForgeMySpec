#!/usr/bin/env python3
"""Expense Splitter CLI — WITHOUT framework. Direct implementation."""
import argparse
import json
import os
import sys

FILE = "expenses.json"

def load():
    if os.path.exists(FILE):
        return json.load(open(FILE))
    return {"expenses": []}

def save(data):
    json.dump(data, open(FILE, "w"), indent=2)

def balances(expenses):
    bal = {}
    for e in expenses:
        payer = e["payer"]
        amt = e["amount"]
        parts = e["participants"]
        share = amt / len(parts)
        bal[payer] = bal.get(payer, 0) + amt - share
        for p in parts:
            if p != payer:
                bal[p] = bal.get(p, 0) - share
    return {k: round(v, 2) for k, v in bal.items()}

def settle(bal):
    creditors = sorted([(n, v) for n, v in bal.items() if v > 0], key=lambda x: -x[1])
    debtors = sorted([(n, -v) for n, v in bal.items() if v < 0], key=lambda x: -x[1])
    txns = []
    c, d = list(creditors), list(debtors)
    ci = di = 0
    while ci < len(c) and di < len(d):
        cn, ca = c[ci]
        dn, da = d[di]
        amt = min(ca, da)
        txns.append({"from": dn, "to": cn, "amount": round(amt, 2)})
        ca -= amt; da -= amt
        if ca < 0.001: ci += 1
        else: c[ci] = (cn, ca)
        if da < 0.001: di += 1
        else: d[di] = (dn, da)
    return txns

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")

a = sub.add_parser("add")
a.add_argument("payer"); a.add_argument("amount")
a.add_argument("--for", dest="for_whom", required=True)
a.add_argument("--description", default="")

sub.add_parser("balances")
sub.add_parser("settle")

args = parser.parse_args()
data = load()

if args.cmd == "add":
    parts = [p.strip() for p in args.for_whom.split(",")]
    data["expenses"].append({
        "id": len(data["expenses"]) + 1,
        "payer": args.payer,
        "amount": float(args.amount),
        "participants": parts,
        "description": args.description
    })
    save(data)
    print(f"Added expense: {args.payer} paid ${float(args.amount):.2f}")

elif args.cmd == "balances":
    bal = balances(data["expenses"])
    for name, v in sorted(bal.items()):
        sign = "+" if v >= 0 else ""
        print(f"  {name}: {sign}${v:.2f}")

elif args.cmd == "settle":
    bal = balances(data["expenses"])
    txns = settle(bal)
    if not txns:
        print("All settled!")
    for i, t in enumerate(txns, 1):
        print(f"  {i}. {t['from']} pays {t['to']} ${t['amount']:.2f}")
