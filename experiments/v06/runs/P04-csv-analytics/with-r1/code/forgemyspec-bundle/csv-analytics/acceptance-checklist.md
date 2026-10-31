# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python module and CLI (csv_analytics.py) that reads CSV files, computes per-column statistics, filters rows, selects columns and exports a JSON report.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Per-column count, min, max, mean, median and stdev match values computed by hand on fixture CSVs.
- [ ] Filters and column selection change which rows and columns appear in the report.
- [ ] The JSON report is valid JSON and contains the stats per column.
- [ ] Bad input (missing file, unknown column, bad filter) exits with code 2 and a message on stderr.

## Required Evidence
- [ ] unittest run output showing all tests in tests/ passing
- [ ] gate report ending in RESULT: PASS
- [ ] sample CLI run output on a fixture CSV showing the JSON report

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, ask for a spec amendment before building it.
- [ ] If a test fails, fix the code, never the test, unless the spec is wrong; then amend the spec.
