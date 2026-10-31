# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (expense_splitter.py) that records group expenses split equally among participants, persists them in a JSON file, shows each person's balance and prints a greedy settlement plan.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] add records an expense and the JSON file contains it after the process exits.
- [ ] balances shows each person's net balance; the balances sum to zero.
- [ ] settle prints transfers that bring every balance to zero using the greedy algorithm.
- [ ] Invalid input exits non-zero with a message on stderr and leaves the file unchanged.

## Required Evidence
- [ ] unittest run of tests/ with all tests passing
- [ ] CLI session output: add, balances and settle on a sample group

## Decision Rules Compliance
- [ ] If the split rule for uneven cents or the settlement semantics are questioned, stop and amend the spec.
- [ ] If any test fails, fix the code, never weaken the test.
