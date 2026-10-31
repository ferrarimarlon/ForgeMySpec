# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (budget_tracker.py) that stores monthly budgets per category and expenses in a JSON file, validates input, reports spending against budget and alerts at 80% and 100%.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Every must_include phrase is exercised by a passing unittest.
- [ ] Rejected input never modifies the JSON file.
- [ ] The report shows spent, budget, percent and status for every budgeted category.

## Required Evidence
- [ ] unittest run output: python3 -m unittest discover -s tests exits 0
- [ ] gate report printing RESULT: PASS

## Decision Rules Compliance
- [ ] If a rule cannot be both faithful to the request and testable, stop and ask the user.
- [ ] Anything beyond the obligations is a spec amendment.
