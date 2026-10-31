# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CSV Analytics Tool
- Objective: Single-file stdlib-only Python tool (csv_analytics.py) that reads CSV files, computes per-column stats, filters rows, selects columns and exports a JSON report.

## Non-Negotiable Guardrails
- Python standard library only; no pandas or third-party packages.
- Everything lives in the single file csv_analytics.py.
- No plotting, no database, no writing formats other than JSON.
- Input files are never modified.

## Decision Rules
- If an ambiguity affects stats semantics (e.g. stdev population vs sample), stop and ask.
- Anything outside the listed features is a spec amendment.

## Success Criteria
- All unittest tests in tests/ pass.
- The CLI produces a valid JSON report for a sample CSV.

## Assumptions
- The first CSV row is the header; column names are the header values.
- A column is numeric if every non-empty cell parses as a float; empty cells are ignored for stats.
- stdev is the sample standard deviation (n-1); it is null when fewer than 2 values.
- Non-numeric columns report count, and min/max by string order; mean, median and stdev are null.
- Filter syntax is COLUMN OP VALUE with OP in ==, !=, <, <=, >, >=; multiple filters are ANDed. Numeric comparison when both sides parse as numbers, else string comparison.
- CLI is argparse-based: csv_analytics.py FILE [--select COLS] [--filter EXPR]... [--output report.json]; JSON goes to stdout when --output is absent.

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
