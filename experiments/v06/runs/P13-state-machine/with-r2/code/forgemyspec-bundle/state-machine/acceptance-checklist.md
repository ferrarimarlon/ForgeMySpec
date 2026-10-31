# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib Python CLI (state_machine.py) that loads a JSON state machine, validates it, runs an event sequence with guards over a context, and prints the transition history.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A valid definition runs an event sequence and prints the history with exit 0.
- [ ] An invalid definition reports every validation error and exits 2.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests pass.
- [ ] CLI output of validate on an invalid definition listing the errors, with exit code 2.
- [ ] CLI output of run on a valid definition printing the transition history.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user.
- [ ] Anything not covered by an obligation is a spec amendment.
