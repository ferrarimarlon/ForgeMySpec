# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (expense_splitter.py) that records group expenses split equally among participants, persists them in a JSON file, shows each person's balance and computes a greedy settlement plan.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] add, list, balances and settle subcommands work end to end against a JSON file.
- [ ] Applying the settlement plan brings every balance to zero.
- [ ] All boundary tests pass under the gate.

## Required Evidence
- [ ] Output of the unittest run for tests/ with all tests passing.
- [ ] Gate report ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If a requirement needs unequal splits or currencies, stop and amend the spec.
- [ ] If a test fails, fix the code, never the test, unless the spec is wrong; then amend.
