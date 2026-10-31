# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (state_machine.py) that loads a state machine from JSON, validates it, runs a sequence of events with guards on a context, and prints the transition history.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A valid machine file runs an event sequence and prints the history.
- [ ] Every validation defect is reported with the offending name.

## Required Evidence
- [ ] Output of python3 -m unittest test_state_machine showing all tests pass.
- [ ] Output of a CLI run printing the history of a sample machine.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous (guard syntax, rejection semantics), stop and ask.
- [ ] If a test fails, fix the code, never weaken the test.
