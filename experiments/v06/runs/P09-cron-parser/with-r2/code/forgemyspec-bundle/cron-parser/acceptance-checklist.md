# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file stdlib-only Python CLI (cron_parser.py) that parses standard 5-field cron expressions, explains them, and computes upcoming run times.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] validate prints a per-field explanation for valid expressions and exits 0.
- [ ] validate prints a clear error naming the offending field and exits non-zero for invalid expressions.
- [ ] next prints exactly N future run times in ascending order, all matching the expression.
- [ ] Expressions that can never fire (such as 0 0 30 2 *) are reported instead of looping forever.

## Required Evidence
- [ ] Output of the unittest run for tests/ showing all tests passing.
- [ ] Command output of validate for a valid and an invalid expression.
- [ ] Command output of next with a fixed reference time showing correct times, including a Feb 29 leap-year case.
- [ ] Command output of next for 0 0 30 2 * showing the never-matches error.

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, treat it as a spec amendment and ask the user.
- [ ] Stop and escalate if the day-of-month/day-of-week semantics conflict with the user's expectation.
