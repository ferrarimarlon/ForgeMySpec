# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CSV Analytics Tool
- Objective: A single-file, stdlib-only Python CLI/library (csv_analytics.py) that reads CSV files, computes per-column statistics, filters rows, selects columns and exports a JSON report.

## Non-Negotiable Guardrails
- Only the Python standard library is used; no third-party packages.
- All code lives in the single file csv_analytics.py.
- No GUI, no database, no network access, no writing of CSV output.
- No aggregation functions beyond count, min, max, mean, median and stdev.

## Decision Rules
- If a filter or stats semantics question arises that the assumptions do not settle, stop and ask the user.
- Anything outside the listed features is a spec amendment.

## Success Criteria
- Running the tool on a CSV prints or writes a JSON report with count, min, max, mean, median and stdev per column.
- Filters and column selection change which rows and columns the report covers.
- Bad input (missing file, unknown column, bad filter) exits non-zero with a clear message.

## Assumptions
- The first CSV row is a header naming the columns.
- A column is numeric for stats when every non-empty cell parses as a float; empty cells are skipped and not counted.
- stdev is the sample standard deviation (n-1); it is null when fewer than 2 values exist.
- Filter syntax is COLUMN OP VALUE with OP in ==, !=, <, <=, >, >=; numeric comparison when both sides parse as numbers, string comparison otherwise; multiple filters are ANDed.
- Non-numeric columns report only count (non-empty cells), and min/max are lexicographic; mean, median and stdev are null.

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
