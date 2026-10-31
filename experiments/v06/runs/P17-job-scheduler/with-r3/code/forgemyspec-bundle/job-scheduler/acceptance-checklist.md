# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (scheduler.py) that manages jobs with priorities and dependencies, persists them in scheduler.json and executes them in dependency order with priority tiebreak.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All boundary tests pass.
- [ ] Every rule of the request is covered by an obligation.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests with all tests passing
- [ ] Gate report ending in RESULT: PASS

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user.
- [ ] Anything outside the obligations is a spec amendment.
