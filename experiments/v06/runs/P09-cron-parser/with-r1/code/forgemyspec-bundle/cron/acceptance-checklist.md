# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (cron_parser.py) that validates standard 5-field cron expressions and prints upcoming run times.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] validate prints a per-field explanation for a valid expression and an error naming the field for an invalid one.
- [ ] next prints N future run times, in ascending order, each matching the expression.
- [ ] Impossible dates such as February 30 never appear in the output.

## Required Evidence
- [ ] unittest run output of the tests folder with all tests passing
- [ ] validate and next command output for sample expressions, including an invalid-date case

## Decision Rules Compliance
- [ ] If a requirement conflicts with standard cron behavior, stop and ask before choosing.
- [ ] Anything outside the obligations is a spec amendment.
