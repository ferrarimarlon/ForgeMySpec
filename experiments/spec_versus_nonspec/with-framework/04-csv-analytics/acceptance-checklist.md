# Acceptance Checklist — CSV Analytics Tool

## Scope
- [x] Only csv_analytics.py produced.
- [x] No external imports (csv, json, statistics, argparse, pathlib, re, sys only).

## Core Stats
- [x] count, min, max, mean, median, stdev correct for numeric cols (age, salary).
- [x] Non-numeric cols (name, department) show count=6, all other stats "-"/null.
- [x] Missing values (Carol's age, Eve's salary) excluded without crash. count=5 for both.

## Filtering
- [x] --filter 'age > 29' reduces to 3 rows with correct recalculated stats.

## Column Selection
- [x] --columns 'age,salary' restricts output to 2 columns only.

## Output
- [x] Table printed with aligned fixed-width columns.
- [x] report.json written; values match stdout table.
- [x] JSON only includes selected columns when --columns used.

## Required Evidence
- [x] Basic run: 4-column CSV with mixed types, correct stats shown.
- [x] --filter: row count reduced from 6 to 3.
- [x] missing.csv: 2 missing values handled; count=2 for each col.

## Issues Found During Implementation
- None. First run passed all checks.
