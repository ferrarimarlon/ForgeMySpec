# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (state_machine.py) that loads a state machine definition from JSON, validates it, runs a sequence of events with guards evaluated on a context, and prints the history of transitions.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A valid definition runs an event sequence and prints each transition as from, event, to.
- [ ] Invalid definitions are reported with all problems and exit 2.
- [ ] All boundary tests pass.

## Required Evidence
- [ ] unittest run of tests/ with all tests passing
- [ ] gate report ending in RESULT: PASS

## Decision Rules Compliance
- [ ] If a requirement needs behavior outside the obligations, stop and amend the spec.
- [ ] Stop and ask when guard semantics or exit codes conflict with the request.
