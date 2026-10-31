# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file stdlib Python CLI (budget_tracker.py) that keeps monthly budgets per category and expenses in a JSON file, reports spending against budgets, and alerts at 80% and 100%.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Budgets can be set and expenses recorded through the CLI and persist in the JSON file.
- [ ] Unknown categories and invalid amounts are rejected with a nonzero exit and the file left unchanged.
- [ ] The report shows spent, budget and percent per category for a month.
- [ ] Alerts appear at 80% and 100% of a category budget.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests pass.
- [ ] Output of the gate command reporting RESULT: PASS.

## Decision Rules Compliance
- [ ] If a rule cannot be both faithful to the request and testable, stop and ask the user.
- [ ] Anything outside the obligations is a spec amendment.
