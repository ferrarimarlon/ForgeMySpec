# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (budget_tracker.py) that keeps monthly budgets per category and expenses in a JSON file, validates input, reports spending against budgets and alerts at 80% and 100%.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] set-budget, add and report subcommands work end to end against a JSON file.
- [ ] Unknown categories and invalid amounts are rejected with a non-zero exit and an error message.
- [ ] Report shows spent, budget and percent per category for a month.
- [ ] Alerts appear at exactly 80% and at 100% of a category budget.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all boundary tests passing.
- [ ] Output of the gate command reporting RESULT PASS.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous (for example rollover or per-month budgets), stop and ask the user.
- [ ] Do not add features outside the three subcommands without a spec amendment.
