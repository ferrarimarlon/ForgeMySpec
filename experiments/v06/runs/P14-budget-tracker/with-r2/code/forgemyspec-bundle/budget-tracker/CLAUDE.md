# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Budget tracker CLI
- Objective: Single-file stdlib Python CLI (budget_tracker.py) that keeps monthly budgets per category and expenses in a JSON file, validates input, reports spending against budgets and alerts at 80% and 100%.

## Non-Negotiable Guardrails
- Single file budget_tracker.py, standard library only, no third-party packages.
- No currency conversion, no recurring expenses, no editing or deleting of expenses, no GUI or network.
- Invalid input never modifies the JSON file.

## Decision Rules
- If a requirement is ambiguous (for example rollover or per-month budgets), stop and ask the user.
- Do not add features outside the three subcommands without a spec amendment.

## Success Criteria
- set-budget, add and report subcommands work end to end against a JSON file.
- Unknown categories and invalid amounts are rejected with a non-zero exit and an error message.
- Report shows spent, budget and percent per category for a month.
- Alerts appear at exactly 80% and at 100% of a category budget.

## Assumptions
- A budget is one monthly limit per category that applies to every calendar month.
- Dates are ISO YYYY-MM-DD; a month is YYYY-MM.
- Amounts are positive decimals with at most 2 decimal places, handled with decimal.Decimal.
- The data file defaults to budget_data.json in the current directory and is overridable with --file.
- Alerts are computed per category for the reported month; report defaults to the current month.
- Subcommands are set-budget, add and report.

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
