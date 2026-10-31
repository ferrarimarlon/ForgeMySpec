# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CLI expense splitter
- Objective: A single-file, stdlib-only Python CLI (expense_splitter.py) that records group expenses split equally among participants, persists them in a JSON file, shows each person's balance and prints a greedy settlement plan.

## Non-Negotiable Guardrails
- Single file expense_splitter.py; no third-party packages.
- No network access, no database, no GUI or web interface.
- No unequal splits, percentages, currency conversion, or expense editing or deletion.
- Money is never held in binary floats after parsing.

## Decision Rules
- If the split rule for uneven cents or the settlement semantics are questioned, stop and amend the spec.
- If any test fails, fix the code, never weaken the test.

## Success Criteria
- add records an expense and the JSON file contains it after the process exits.
- balances shows each person's net balance; the balances sum to zero.
- settle prints transfers that bring every balance to zero using the greedy algorithm.
- Invalid input exits non-zero with a message on stderr and leaves the file unchanged.

## Assumptions
- Amounts are decimal currency with at most 2 decimals, stored as integer cents to avoid float drift.
- When the amount does not divide evenly, the leftover cents go one each to the first participants in the listed order, so shares always sum to the amount.
- The payer need not be among the participants.
- Greedy settlement means repeatedly matching the largest creditor with the largest debtor; this yields at most n-1 transfers but is not guaranteed the global minimum in every case.
- The data file defaults to expenses.json in the current directory and can be overridden with --file.

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
