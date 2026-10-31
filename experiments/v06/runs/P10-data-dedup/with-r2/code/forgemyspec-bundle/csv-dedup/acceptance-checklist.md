# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Provide data_dedup.py, a stdlib-only single-file Python CLI that removes duplicate CSV rows by a composite key using keep-first, keep-last or error strategies, writes an output CSV and prints a summary.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Composite keys of one or more columns dedupe correctly under first, last and error strategies.
- [ ] Error strategy exits non-zero and lists the duplicate keys with row numbers.
- [ ] Summary prints duplicates found and removed.

## Required Evidence
- [ ] unittest run output of tests/ with all tests passing
- [ ] forgemyspec gate report showing RESULT: PASS

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, stop and request a spec amendment.
- [ ] If the gate fails, fix the implementation, never the tests or the spec.
