# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CLI expense splitter
- Objective: A single-file, stdlib-only Python CLI (expense_splitter.py) that records group expenses split equally among participants, persists them in a JSON file, shows each person's balance and computes a greedy settlement plan.

## Non-Negotiable Guardrails
- Single file expense_splitter.py; standard library only, no third-party packages.
- No floating-point money arithmetic.
- No unequal or percentage splits, currencies, expense editing or deletion, or network access.

## Decision Rules
- If a requirement needs unequal splits or currencies, stop and amend the spec.
- If a test fails, fix the code, never the test, unless the spec is wrong; then amend.

## Success Criteria
- add, list, balances and settle subcommands work end to end against a JSON file.
- Applying the settlement plan brings every balance to zero.
- All boundary tests pass under the gate.

## Assumptions
- Amounts are decimal with at most 2 places and are stored as integer cents to avoid float error.
- When an amount does not divide evenly, the leftover cents go one each to the first participants in sorted name order, so shares always sum exactly to the amount.
- The payer need not be a participant; a payer outside the participants is credited the full amount and owes nothing.
- Greedy (largest creditor paid by largest debtor) gives at most n-1 transfers; it is not guaranteed to be the true minimum, which is NP-hard in general.
- Names are case-sensitive, non-empty strings; the default data file is expenses.json in the current directory, overridable with --file.

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
