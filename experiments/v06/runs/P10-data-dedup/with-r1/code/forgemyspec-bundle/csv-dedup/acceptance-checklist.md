# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (data_dedup.py) that removes duplicate CSV rows by a composite key using keep-first, keep-last or error strategies, writes an output CSV and prints a summary.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Composite keys over one or more columns dedupe correctly with all three strategies.
- [ ] Summary line reports duplicates found and removed.
- [ ] Error strategy exits non-zero and lists the duplicate keys.

## Required Evidence
- [ ] unittest run output of tests/test_data_dedup.py with all tests passing
- [ ] gate command output ending in RESULT: PASS

## Decision Rules Compliance
- [ ] Stop and ask if a requirement needs behavior outside the listed obligations.
