# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (scheduler.py) that manages jobs with dependencies and priorities, persisted in scheduler.json.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All ten requirements are covered by passing unittest tests.

## Required Evidence
- [ ] Output of the unittest run over tests/ with all tests passing.
- [ ] Output of the gate for the bundle ending in RESULT PASS.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user.
- [ ] Anything outside the ten requirements is a spec amendment.
