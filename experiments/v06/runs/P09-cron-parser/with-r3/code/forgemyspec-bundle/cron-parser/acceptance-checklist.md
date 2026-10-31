# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (cron_parser.py) that parses standard 5-field cron expressions, explains them with validate, and prints upcoming run times with next.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] validate prints one explanation line per field for a valid expression and exits 0.
- [ ] validate names the field and the reason for an invalid expression and exits 2.
- [ ] next prints N future run times, ascending, each matching the expression.
- [ ] Impossible dates such as 0 0 30 2 * are reported, never looped on forever.

## Required Evidence
- [ ] unittest run of tests/test_cron_parser.py with all tests passing
- [ ] output of cron_parser.py validate for a valid and an invalid expression
- [ ] output of cron_parser.py next for a normal expression and for 0 0 30 2 *

## Decision Rules Compliance
- [ ] Stop and ask if a requirement needs anything beyond the standard library or a second file.
- [ ] Treat any behavior not covered by an obligation as a spec amendment.
