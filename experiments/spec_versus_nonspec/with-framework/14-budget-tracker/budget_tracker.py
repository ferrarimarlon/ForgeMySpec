#!/usr/bin/env python3
"""Budget Tracker CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: category validation, 80% near-limit alert, reset preserves budgets.
"""
import argparse
import json
import os
import sys

DATA_FILE = "budget.json"


def load_data(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"budgets": {}, "expenses": []}


def save_data(data: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def compute_spent(expenses: list, category: str) -> float:
    return sum(e["amount"] for e in expenses if e["category"] == category)


def cmd_set_budget(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    amount = float(args.amount)
    if amount < 0:
        print("Error: budget amount cannot be negative.", file=sys.stderr)
        sys.exit(1)
    data["budgets"][args.category] = amount
    save_data(data, args.file)
    print(f"Budget set: {args.category} = ${amount:.2f}")


def cmd_add_expense(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    if args.category not in data["budgets"]:
        print(
            f"Error: category '{args.category}' not found. Set a budget first.",
            file=sys.stderr,
        )
        sys.exit(1)
    amount = float(args.amount)
    if amount < 0:
        print("Error: expense amount cannot be negative.", file=sys.stderr)
        sys.exit(1)
    expense = {
        "category": args.category,
        "amount": amount,
        "note": args.note or "",
    }
    data["expenses"].append(expense)
    save_data(data, args.file)
    spent = compute_spent(data["expenses"], args.category)
    budget = data["budgets"][args.category]
    pct = round(spent / budget * 100, 1) if budget > 0 else 0.0
    print(f"Added expense: {args.category} ${amount:.2f} (total: ${spent:.2f} / ${budget:.2f} = {pct}%)")


def cmd_summary(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    if not data["budgets"]:
        print("No budgets set.")
        return
    print(f"{'Category':<20} {'Budget':>10} {'Spent':>10} {'Remaining':>10} {'% Used':>8}")
    print("-" * 62)
    for cat, budget in sorted(data["budgets"].items()):
        spent = compute_spent(data["expenses"], cat)
        remaining = budget - spent
        pct = round(spent / budget * 100, 1) if budget > 0 else 0.0
        remaining_str = f"${remaining:.2f}" if remaining >= 0 else f"-${abs(remaining):.2f}"
        print(f"{cat:<20} ${budget:>9.2f} ${spent:>9.2f} {remaining_str:>10} {pct:>7.1f}%")


def cmd_alert(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    if not data["budgets"]:
        print("No budgets set.")
        return
    alerts = []
    for cat, budget in sorted(data["budgets"].items()):
        spent = compute_spent(data["expenses"], cat)
        pct = round(spent / budget * 100, 1) if budget > 0 else 0.0
        if spent > budget:
            alerts.append((cat, pct, "OVER BUDGET"))
        elif pct > 80:
            alerts.append((cat, pct, "NEAR LIMIT"))
    if not alerts:
        print("All categories within budget.")
        return
    print(f"Alerts ({len(alerts)}):")
    for cat, pct, status in alerts:
        print(f"  [{status}] {cat}: {pct}% used")


def cmd_reset(args: argparse.Namespace) -> None:
    data = load_data(args.file)
    data["expenses"] = []
    save_data(data, args.file)
    print("Expenses cleared. Budgets preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Budget Tracker CLI")
    parser.add_argument("--file", default=DATA_FILE, help="Data file path")
    sub = parser.add_subparsers(dest="command")

    p_sb = sub.add_parser("set-budget", help="Set category budget")
    p_sb.add_argument("category", help="Category name")
    p_sb.add_argument("amount", help="Budget amount")

    p_ae = sub.add_parser("add-expense", help="Add an expense")
    p_ae.add_argument("category", help="Category name")
    p_ae.add_argument("amount", help="Expense amount")
    p_ae.add_argument("--note", help="Optional note")

    sub.add_parser("summary", help="Show budget summary table")
    sub.add_parser("alert", help="Show budget alerts")
    sub.add_parser("reset", help="Clear expenses (keep budgets)")

    args = parser.parse_args()
    if args.command == "set-budget":
        cmd_set_budget(args)
    elif args.command == "add-expense":
        cmd_add_expense(args)
    elif args.command == "summary":
        cmd_summary(args)
    elif args.command == "alert":
        cmd_alert(args)
    elif args.command == "reset":
        cmd_reset(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
