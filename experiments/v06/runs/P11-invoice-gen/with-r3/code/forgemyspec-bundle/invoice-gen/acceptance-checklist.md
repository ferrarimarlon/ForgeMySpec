# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file stdlib-only Python CLI (invoice_gen.py) that reads an invoice JSON, validates it reporting all errors at once, computes totals with correct money rounding, and prints a text invoice or exports JSON.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All validation errors of an invalid invoice are printed in one run.
- [ ] Totals match hand-computed values including half-cent cases.
- [ ] Text and JSON outputs both work from the CLI.

## Required Evidence
- [ ] unittest run of tests/test_invoice_gen.py with all tests passing
- [ ] CLI output of a sample invoice in text and JSON formats

## Decision Rules Compliance
- [ ] If an input rule is ambiguous, stop and ask rather than guess.
- [ ] Anything beyond these obligations is a spec amendment.
