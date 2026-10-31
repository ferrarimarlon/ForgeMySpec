# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CSV deduplicator CLI
- Objective: Provide data_dedup.py, a stdlib-only single-file Python CLI that removes duplicate CSV rows by a composite key using keep-first, keep-last or error strategies, writes an output CSV and prints a summary.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- All code lives in the single file data_dedup.py.
- No fuzzy matching, no in-place editing of the input, no formats other than CSV.
- In error strategy no output file is written.

## Decision Rules
- If a behavior is not covered by an obligation, stop and request a spec amendment.
- If the gate fails, fix the implementation, never the tests or the spec.

## Success Criteria
- Composite keys of one or more columns dedupe correctly under first, last and error strategies.
- Error strategy exits non-zero and lists the duplicate keys with row numbers.
- Summary prints duplicates found and removed.

## Assumptions
- The input CSV has a header row; key columns are selected by header name.
- Rows are compared by exact string equality of the key column values (no trimming or case folding).
- Input and output are UTF-8 with csv module default dialect handling; output keeps the input header and column order.
- Surviving rows keep their original relative order; with keep-last the survivor sits at the position of the last occurrence.
- A duplicate is any row beyond the first sharing a key; found count equals rows minus distinct keys.

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
