# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Budget tracker CLI
- Objective: Single-file stdlib Python CLI (budget_tracker.py) that stores monthly budgets per category and expenses in a JSON file, validates input, reports spending against budget and alerts at 80% and 100%.

## Non-Negotiable Guardrails
- Single file budget_tracker.py, Python standard library only.
- No third-party dependencies, no network access.
- No multi-currency, no recurring expenses, no editing or deleting recorded expenses.
- No GUI or web interface; command line only.

## Decision Rules
- If a rule cannot be both faithful to the request and testable, stop and ask the user.
- Anything beyond the obligations is a spec amendment.

## Success Criteria
- Every must_include phrase is exercised by a passing unittest.
- Rejected input never modifies the JSON file.
- The report shows spent, budget, percent and status for every budgeted category.

## Assumptions
- Amounts are decimal money values with at most 2 decimal places, parsed with decimal.Decimal and stored in JSON as strings (no floats).
- A budget is a monthly limit per category and applies to every month until changed with set-budget.
- A category is known if and only if it has a budget; there is no separate category registry.
- Dates are ISO YYYY-MM-DD; when omitted the expense date is today. The report covers one calendar month, default the current month.
- Usage errors and validation errors exit with status 2 and print the reason on stderr; success exits 0.
- Alert thresholds compare spent against budget exactly with Decimal: spent*100 >= budget*80 is the warning, spent >= budget the exceeded alert.

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
