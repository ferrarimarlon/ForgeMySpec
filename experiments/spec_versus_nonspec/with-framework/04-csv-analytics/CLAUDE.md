# CLAUDE.md — CSV Analytics Tool

## Role
Implement csv_analytics.py strictly from spec.yaml.

## Non-Negotiable Guardrails
- Single file: csv_analytics.py only.
- stdlib only — no pandas/numpy.
- Stats: count, min, max, mean, median, stdev (numeric); count only (non-numeric).
- Single --filter expression; --columns is comma-separated.
- report.json keys per column: count, min, max, mean, median, stdev.

## Decision Rules
- stdev < 2 values → 0.0.
- Empty cell → skip from numerics.
- Filter error → exit 1.
- Unknown column in --filter/--columns → warn, skip.
- Directory with no CSV → exit 1.
- Table widths: ColName(20)|Count(6)|Min(10)|Max(10)|Mean(10)|Median(10)|Stdev(10).

## Known Pitfalls
- statistics.stdev raises StatisticsError if len < 2 — wrap in try/except, return 0.0.
- float coercion for filter value must be tried before string comparison for numeric cols.
- csv.DictReader fieldnames may have leading/trailing whitespace — strip them.
- When input is a directory, glob for *.csv; if empty, exit 1 with message.
- JSON serialization: round floats to 4 decimal places for readability.
