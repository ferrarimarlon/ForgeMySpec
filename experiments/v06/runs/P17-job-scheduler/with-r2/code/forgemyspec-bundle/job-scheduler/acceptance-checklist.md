# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (scheduler.py) that manages jobs with dependencies and priorities, persisted in scheduler.json.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All boundary tests in tests/ pass.
- [ ] Every rejected add leaves scheduler.json unchanged.
- [ ] A failed job cancels every transitive dependent and no others.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests passing.
- [ ] Output of the forgemyspec gate for the bundle ending in RESULT PASS.

## Decision Rules Compliance
- [ ] Stop and ask if a requirement conflicts with another or cannot be tested.
- [ ] Any behavior outside the listed requirements is a spec amendment.
