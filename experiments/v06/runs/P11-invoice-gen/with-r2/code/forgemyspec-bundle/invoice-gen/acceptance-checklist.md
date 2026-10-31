# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (invoice_gen.py) that reads an invoice JSON, validates it reporting all errors at once, computes line totals, subtotal, discount, tax and grand total with correct money rounding, and prints a formatted text invoice or exports JSON.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] An invalid invoice prints every validation error at once and exits 2.
- [ ] Totals for a valid invoice match hand-computed values including half-cent rounding cases.
- [ ] Text and JSON outputs show the same computed amounts.

## Required Evidence
- [ ] unittest run of tests/ with all tests passing
- [ ] CLI run on a valid sample printing the text invoice
- [ ] CLI run on an invalid sample listing all errors and exit code 2

## Decision Rules Compliance
- [ ] If the discount or tax semantics in the assumptions are wrong, stop and amend the spec.
- [ ] If a rule cannot be tested at the boundary, escalate instead of weakening it.
