# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CSV deduplicator CLI
- Objective: Single-file stdlib Python CLI (data_dedup.py) that removes duplicate CSV rows by a composite key using keep-first, keep-last or error strategies, writes an output CSV and prints a summary.

## Non-Negotiable Guardrails
- Python standard library only, no third-party packages.
- Everything lives in the single file data_dedup.py.
- No fuzzy or normalized matching, no in-place modification of the input file.
- The error strategy writes no output file.

## Decision Rules
- If a behavior is not covered by an obligation, ask for a spec amendment before adding it.

## Success Criteria
- Unit tests pass for all three strategies, composite keys, summary and error exit.

## Assumptions
- The input CSV has a header row; key columns are named by header.
- Keys compare exact string values (case-sensitive, no trimming).
- Duplicates found means rows beyond the first occurrence of each key.
- Surviving rows keep their original relative order; keep-last keeps the position of the last occurrence.
- Exit codes: 0 success, 1 duplicates found under the error strategy, 2 usage or input problems.

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
