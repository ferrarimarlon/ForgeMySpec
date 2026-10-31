# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI/library (csv_analytics.py) that reads CSV files, computes per-column statistics, filters rows, selects columns and exports a JSON report.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Running the tool on a CSV prints or writes a JSON report with count, min, max, mean, median and stdev per column.
- [ ] Filters and column selection change which rows and columns the report covers.
- [ ] Bad input (missing file, unknown column, bad filter) exits non-zero with a clear message.

## Required Evidence
- [ ] unittest run output of tests/ with all tests passing
- [ ] gate command output ending in RESULT: PASS
- [ ] sample CLI run output showing the JSON report

## Decision Rules Compliance
- [ ] If a filter or stats semantics question arises that the assumptions do not settle, stop and ask the user.
- [ ] Anything outside the listed features is a spec amendment.
