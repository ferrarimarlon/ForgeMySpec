# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Budget tracker CLI
- Objective: A single-file stdlib Python CLI (budget_tracker.py) that keeps monthly budgets per category and expenses in a JSON file, reports spending against budgets, and alerts at 80% and 100%.

## Non-Negotiable Guardrails
- Only the Python standard library is used.
- All code lives in the single file budget_tracker.py.
- No network access, no database, no GUI.
- Categories exist only when a budget has been defined; no implicit category creation by add.
- Floats are never used for money.

## Decision Rules
- If a rule cannot be both faithful to the request and testable, stop and ask the user.
- Anything outside the obligations is a spec amendment.

## Success Criteria
- Budgets can be set and expenses recorded through the CLI and persist in the JSON file.
- Unknown categories and invalid amounts are rejected with a nonzero exit and the file left unchanged.
- The report shows spent, budget and percent per category for a month.
- Alerts appear at 80% and 100% of a category budget.

## Assumptions
- Budgets are one amount per category per month, keyed by YYYY-MM.
- Amounts are decimal with at most 2 fractional digits; stored in JSON as strings to avoid float error.
- Expense dates are ISO YYYY-MM-DD; the month of the date selects the budget.
- The data file defaults to budget.json and is overridable with --file.
- Alert thresholds are inclusive: spent >= 80% of budget warns, spent >= 100% marks exceeded.
- An expense in a month where its category has no budget is accepted for known categories, and reported with no alert.

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- (record stable architecture or policy decisions here)

## Known Pitfalls
- (record recurring implementation failure modes here)
