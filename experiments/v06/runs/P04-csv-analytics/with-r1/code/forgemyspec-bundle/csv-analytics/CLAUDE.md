# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CSV Analytics Tool
- Objective: A single-file, stdlib-only Python module and CLI (csv_analytics.py) that reads CSV files, computes per-column statistics, filters rows, selects columns and exports a JSON report.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- All code lives in the single file csv_analytics.py.
- No plotting, no database, no network access, no writing back to the CSV.
- No support for multiple input files in one report.

## Decision Rules
- If a behavior is not covered by an obligation, ask for a spec amendment before building it.
- If a test fails, fix the code, never the test, unless the spec is wrong; then amend the spec.

## Success Criteria
- Per-column count, min, max, mean, median and stdev match values computed by hand on fixture CSVs.
- Filters and column selection change which rows and columns appear in the report.
- The JSON report is valid JSON and contains the stats per column.
- Bad input (missing file, unknown column, bad filter) exits with code 2 and a message on stderr.

## Assumptions
- The first CSV row is the header; column names are unique and non-empty.
- A column is numeric when every non-empty cell parses as a float; stats for non-numeric columns report count only, with min/max/mean/median/stdev as null.
- Empty cells are missing values and are excluded from count and from stats.
- stdev is the sample standard deviation (n-1); it is null when fewer than 2 values exist.
- Filter syntax is COLUMN OP VALUE with OP in ==, !=, <, <=, >, >=; numeric comparison when both sides parse as numbers, string comparison otherwise; multiple filters are ANDed.
- Stats are computed after filtering and column selection, over the remaining rows and columns.
- The CLI is: csv_analytics.py FILE [--filter EXPR]... [--columns A,B] [--output report.json]; without --output the JSON goes to stdout.

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
