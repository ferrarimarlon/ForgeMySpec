# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Replay a ledger of deposits and withdrawals from an opening balance, rejecting overdrafts and non-positive amounts, with the arithmetic proven in Dafny and exposed to users through a small Python command-line shell.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] `python3 -m forgemyspec gate examples/budget-core` exits 0 with every stage PASS.
- [ ] Replaying `deposit 10, withdraw 4, withdraw 7, deposit -1, deposit 2` from 0 prints `balance=8 rejected=2`.
- [ ] A malformed ledger line makes the CLI exit 2 and name the line number on stderr.

## Required Evidence
- [ ] Gate report for this bundle with every stage PASS, including the mutation kill rate.
- [ ] Output of the Python boundary tests run against generated/core-py.

## Decision Rules Compliance
- [ ] If a contract clause turns out to be unprovable as written, stop and amend the spec and contract with user approval instead of weakening impl.dfy.
- [ ] If a mutant or a planted error survives, strengthen tests.dfy or the contract through re-approval, or justify an equivalent mutant in impl.dfy.
