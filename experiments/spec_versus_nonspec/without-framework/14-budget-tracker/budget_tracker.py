#!/usr/bin/env python3
"""Budget Tracker — WITHOUT framework. Direct implementation."""
import argparse
import json
import os
import sys

FILE = "budget.json"

def load():
    if os.path.exists(FILE): return json.load(open(FILE))
    return {"budgets": {}, "expenses": []}

def save(d): json.dump(d, open(FILE, "w"), indent=2)

def spent(expenses, cat):
    return sum(e["amount"] for e in expenses if e["category"] == cat)

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
sb = sub.add_parser("set-budget"); sb.add_argument("category"); sb.add_argument("amount")
ae = sub.add_parser("add-expense")
ae.add_argument("category"); ae.add_argument("amount"); ae.add_argument("--note", default="")
sub.add_parser("summary"); sub.add_parser("alert"); sub.add_parser("reset")

args = parser.parse_args()
data = load()

if args.cmd == "set-budget":
    data["budgets"][args.category] = float(args.amount)
    save(data)
    print(f"Budget set: {args.category} = ${float(args.amount):.2f}")

elif args.cmd == "add-expense":
    if args.category not in data["budgets"]:
        print(f"Error: no budget for '{args.category}'", file=sys.stderr); sys.exit(1)
    data["expenses"].append({"category": args.category, "amount": float(args.amount), "note": args.note})
    save(data)
    s = spent(data["expenses"], args.category)
    b = data["budgets"][args.category]
    print(f"Added: {args.category} ${float(args.amount):.2f} (total ${s:.2f} / ${b:.2f})")

elif args.cmd == "summary":
    if not data["budgets"]: print("No budgets"); sys.exit(0)
    print(f"{'Category':<20} {'Budget':>10} {'Spent':>10} {'Remaining':>10} {'%':>8}")
    print("-" * 62)
    for cat, bgt in sorted(data["budgets"].items()):
        s = spent(data["expenses"], cat)
        rem = bgt - s
        pct = round(s/bgt*100, 1) if bgt else 0
        print(f"{cat:<20} ${bgt:>9.2f} ${s:>9.2f} ${rem:>9.2f} {pct:>7.1f}%")

elif args.cmd == "alert":
    alerts = []
    for cat, bgt in data["budgets"].items():
        s = spent(data["expenses"], cat)
        pct = round(s/bgt*100, 1) if bgt else 0
        if s > bgt: alerts.append((cat, pct, "OVER"))
        elif pct > 80: alerts.append((cat, pct, "NEAR"))
    if not alerts: print("All within budget")
    for cat, pct, status in alerts:
        print(f"  [{status}] {cat}: {pct}%")

elif args.cmd == "reset":
    data["expenses"] = []
    save(data)
    print("Expenses cleared")
