#!/usr/bin/env python3
"""Expense splitter: record group expenses, show balances, compute a settlement plan.

Single file, standard library only. Money is kept as integer cents.
"""
import argparse
import json
import os
import re
import sys
import tempfile

DEFAULT_FILE = "expenses.json"
_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")


class LedgerError(Exception):
    """Invalid input or corrupt data file; the CLI maps it to exit status 2."""


def parse_amount(text):
    """Parse a positive decimal string with at most 2 places into integer cents."""
    text = str(text).strip()
    if not _AMOUNT_RE.match(text):
        raise LedgerError("invalid amount %r: use a positive number with at most 2 decimals" % text)
    whole, _, frac = text.partition(".")
    cents = int(whole) * 100 + int((frac + "00")[:2])
    if cents <= 0:
        raise LedgerError("invalid amount %r: must be greater than zero" % text)
    return cents


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def split_shares(amount_cents, participants):
    """Equal split; leftover cents go one each to the first participants in sorted order."""
    names = sorted(set(participants))
    if not names:
        raise LedgerError("an expense needs at least one participant")
    base, extra = divmod(amount_cents, len(names))
    return {n: base + (1 if i < extra else 0) for i, n in enumerate(names)}


def make_expense(payer, amount, description, participants):
    payer = (payer or "").strip()
    names = [p.strip() for p in participants]
    if not payer:
        raise LedgerError("payer must not be empty")
    if not names or any(not n for n in names):
        raise LedgerError("participants must be a non-empty list of non-empty names")
    return {
        "payer": payer,
        "amount_cents": parse_amount(amount),
        "description": description,
        "participants": sorted(set(names)),
    }


def _validate(data):
    if not isinstance(data, dict) or not isinstance(data.get("expenses"), list):
        raise LedgerError("data file must be an object with an 'expenses' list")
    for i, e in enumerate(data["expenses"], 1):
        ok = (
            isinstance(e, dict)
            and isinstance(e.get("payer"), str) and e["payer"]
            and isinstance(e.get("amount_cents"), int) and not isinstance(e["amount_cents"], bool)
            and e["amount_cents"] > 0
            and isinstance(e.get("description"), str)
            and isinstance(e.get("participants"), list) and e["participants"]
            and all(isinstance(p, str) and p for p in e["participants"])
        )
        if not ok:
            raise LedgerError("expense #%d in data file is malformed" % i)
    return data["expenses"]


def load(path):
    """Return the list of expenses; a missing file is an empty ledger."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LedgerError("corrupt JSON in %s: %s" % (path, exc))
    except OSError as exc:
        raise LedgerError("cannot read %s: %s" % (path, exc))
    return _validate(data)


def save(path, expenses):
    """Write atomically so a failure never leaves a half-written file."""
    directory = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".expenses-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"expenses": expenses}, f, indent=2)
                f.write("\n")
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    except OSError as exc:
        raise LedgerError("cannot write %s: %s" % (path, exc))


def balances(expenses):
    """Net balance in cents per person: paid minus share. Positive = is owed."""
    result = {}
    for e in expenses:
        result[e["payer"]] = result.get(e["payer"], 0) + e["amount_cents"]
        for name, share in split_shares(e["amount_cents"], e["participants"]).items():
            result[name] = result.get(name, 0) - share
    return result


def settle_plan(bal):
    """Greedy: repeatedly the largest debtor pays the largest creditor.

    Each transfer settles at least one person, so there are at most n-1 transfers.
    Returns a list of (debtor, creditor, cents).
    """
    debtors = {n: -v for n, v in bal.items() if v < 0}
    creditors = {n: v for n, v in bal.items() if v > 0}
    plan = []
    while debtors and creditors:
        d = max(sorted(debtors), key=lambda n: debtors[n])
        c = max(sorted(creditors), key=lambda n: creditors[n])
        amount = min(debtors[d], creditors[c])
        plan.append((d, c, amount))
        debtors[d] -= amount
        creditors[c] -= amount
        if debtors[d] == 0:
            del debtors[d]
        if creditors[c] == 0:
            del creditors[c]
    return plan


def build_parser():
    p = argparse.ArgumentParser(description="Split group expenses equally and settle up.")
    p.add_argument("--file", default=DEFAULT_FILE, help="JSON data file (default: %(default)s)")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="record an expense")
    a.add_argument("--payer", required=True)
    a.add_argument("--amount", required=True, help="e.g. 42.50")
    a.add_argument("--description", required=True)
    a.add_argument("--participants", required=True, nargs="+", help="people sharing the expense")
    sub.add_parser("list", help="list recorded expenses")
    sub.add_parser("balances", help="show each person's balance")
    sub.add_parser("settle", help="show a settlement plan")
    return p


def run(args, out):
    if args.command == "add":
        expense = make_expense(args.payer, args.amount, args.description, args.participants)
        expenses = load(args.file)
        expenses.append(expense)
        save(args.file, expenses)
        print("Recorded %s paid %s for %s (%d participants)" % (
            expense["payer"], format_cents(expense["amount_cents"]),
            expense["description"], len(expense["participants"])), file=out)
        return
    expenses = load(args.file)
    if args.command == "list":
        for i, e in enumerate(expenses, 1):
            print("%d. %s paid %s for %s, split among %s" % (
                i, e["payer"], format_cents(e["amount_cents"]), e["description"],
                ", ".join(e["participants"])), file=out)
    elif args.command == "balances":
        for name, cents in sorted(balances(expenses).items()):
            print("%s: %s" % (name, format_cents(cents)), file=out)
    elif args.command == "settle":
        plan = settle_plan(balances(expenses))
        if not plan:
            print("All settled.", file=out)
        for d, c, cents in plan:
            print("%s pays %s %s" % (d, c, format_cents(cents)), file=out)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run(args, sys.stdout)
    except LedgerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
