# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CLI expense splitter
- Objective: A single-file, stdlib-only Python CLI (expense_splitter.py) that records group expenses split equally, persists them in a JSON file, shows balances and computes a greedy settlement plan.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- All code lives in the single file expense_splitter.py.
- No networking, currencies, or recurring expenses; no unequal or percentage splits.
- Floats are never used to store or sum money.

## Decision Rules
- If a requirement needs a non-stdlib package, stop and ask.
- If rounding policy conflicts with the user's expectation, escalate.

## Success Criteria
- Adding expenses then running balances prints each person's net balance, and balances sum to zero.
- The settlement plan, when applied, brings every balance to zero.
- Data survives across separate CLI invocations via the JSON file.

## Assumptions
- Amounts are decimal with at most 2 places and are stored as integer cents to avoid float error.
- When an amount does not divide evenly, leftover cents go one each to the first participants in listed order, so shares always sum to the amount.
- The payer need not be a participant; a payer outside the participant list pays without owing a share.
- The data file defaults to expenses.json in the current directory and is overridable with --file.
- Greedy means repeatedly matching the largest debtor with the largest creditor; it is not guaranteed globally minimal for every input.

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
