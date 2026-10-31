# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (invoice_gen.py) that reads an invoice JSON, validates it reporting all errors at once, computes totals with correct money rounding, and prints a text invoice or exports JSON.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A valid invoice prints a formatted text invoice and the same figures export as JSON.
- [ ] An invoice with several defects lists every defect in one run.
- [ ] Rounding cases such as 0.005 and 1.005 totals round half-up to the cent.

## Required Evidence
- [ ] unittest run of tests/ exits 0 with all tests passing.
- [ ] Command output of invoice_gen.py on a valid sample showing the text invoice and the JSON export.
- [ ] Command output of invoice_gen.py on a multi-defect sample listing all errors and exiting 1.

## Decision Rules Compliance
- [ ] If a rule is ambiguous (discount shape, tax base), stop and amend the spec instead of guessing.
- [ ] Stop when any test fails; do not weaken tests.
