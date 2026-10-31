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
- Single file data_dedup.py using only the Python standard library.
- No fuzzy matching, no sorting, no in-place overwrite of the input, no third-party packages.
- Under the error strategy no output file is written.

## Decision Rules
- Stop and ask if a requirement needs behavior outside the listed obligations.

## Success Criteria
- Composite keys over one or more columns dedupe correctly with all three strategies.
- Summary line reports duplicates found and removed.
- Error strategy exits non-zero and lists the duplicate keys.

## Assumptions
- Input CSV has a header row; key columns are named by header.
- A duplicate is any row beyond the first sharing the same key tuple; found count = rows minus unique keys.
- Surviving rows keep their original relative order; keep-last orders by position of the last occurrence.
- Key values are compared as exact strings, no trimming or case folding.
- Exit codes: 0 success, 1 duplicates under the error strategy, 2 usage or input problems.

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
