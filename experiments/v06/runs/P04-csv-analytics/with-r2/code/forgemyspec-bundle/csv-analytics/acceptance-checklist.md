# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib-only Python tool (csv_analytics.py) that reads CSV files, computes per-column stats, filters rows, selects columns and exports a JSON report.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All unittest tests in tests/ pass.
- [ ] The CLI produces a valid JSON report for a sample CSV.

## Required Evidence
- [ ] Output of python3 -m unittest discover tests showing all tests passing.
- [ ] CLI run output on a sample CSV showing the JSON report.

## Decision Rules Compliance
- [ ] If an ambiguity affects stats semantics (e.g. stdev population vs sample), stop and ask.
- [ ] Anything outside the listed features is a spec amendment.
