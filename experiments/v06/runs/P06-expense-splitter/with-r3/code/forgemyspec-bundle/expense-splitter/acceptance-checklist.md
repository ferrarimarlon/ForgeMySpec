# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (expense_splitter.py) that records group expenses split equally, persists them in a JSON file, shows balances and computes a greedy settlement plan.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Adding expenses then running balances prints each person's net balance, and balances sum to zero.
- [ ] The settlement plan, when applied, brings every balance to zero.
- [ ] Data survives across separate CLI invocations via the JSON file.

## Required Evidence
- [ ] unittest run output of tests/ showing all tests pass
- [ ] CLI transcript of add, balances and settle on a temporary JSON file

## Decision Rules Compliance
- [ ] If a requirement needs a non-stdlib package, stop and ask.
- [ ] If rounding policy conflicts with the user's expectation, escalate.
