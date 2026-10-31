"""Thin I/O shell over the verified core in generated/core-py.

Everything here is boundary code: reading the ledger file, enforcing the core's
preconditions (Dafny does not check `requires` clauses at runtime), and printing.
The ledger arithmetic itself lives only in the Dafny-verified BudgetImpl module.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Tuple

import _dafny
import BudgetImpl


class LedgerError(ValueError):
    pass


def parse_ledger(text: str) -> List[BudgetImpl.Tx]:
    txs = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] not in {"deposit", "withdraw"}:
            raise LedgerError(f"line {number}: expected 'deposit <int>' or 'withdraw <int>', got {raw!r}")
        try:
            amount = int(parts[1])
        except ValueError:
            raise LedgerError(f"line {number}: amount is not an integer: {parts[1]!r}") from None
        txs.append(BudgetImpl.Tx_Deposit(amount) if parts[0] == "deposit" else BudgetImpl.Tx_Withdraw(amount))
    return txs


def replay(start: int, txs: List[BudgetImpl.Tx]) -> Tuple[int, int]:
    if start < 0:
        raise LedgerError("start balance must be >= 0")
    final, rejected = BudgetImpl.default__.ApplyAll(start, _dafny.SeqWithoutIsStrInference(txs))
    return final, rejected


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replay a ledger file through the verified budget core.")
    parser.add_argument("ledger", help="File with one 'deposit <int>' or 'withdraw <int>' per line.")
    parser.add_argument("--start", type=int, default=0, help="Opening balance (must be >= 0).")
    args = parser.parse_args(argv)

    try:
        with open(args.ledger, "r", encoding="utf-8") as handle:
            txs = parse_ledger(handle.read())
        final, rejected = replay(args.start, txs)
    except (OSError, LedgerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"balance={final} rejected={rejected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
