# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (scheduler.py) that manages jobs with dependencies and priorities, persisted in scheduler.json.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Every obligation test passes.
- [ ] scheduler.json never contains the status ready.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests with all tests passing.
- [ ] Gate report ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user.
- [ ] If a test fails, fix scheduler.py; never weaken the tests.
