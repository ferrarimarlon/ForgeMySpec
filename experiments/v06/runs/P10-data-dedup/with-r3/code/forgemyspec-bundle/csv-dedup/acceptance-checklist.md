# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (data_dedup.py) that removes duplicate CSV rows by a composite key using keep-first, keep-last or error strategies, writes an output CSV and prints a summary.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Unit tests pass for all three strategies, composite keys, summary and error exit.

## Required Evidence
- [ ] Output of python3 -m unittest discover tests showing all tests passing.
- [ ] Output of a sample CLI run showing the summary line and the output CSV.

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, ask for a spec amendment before adding it.
