# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (time_tracker.py) that tracks work sessions per project in a JSON file.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All subcommands behave as specified in the boundary tests.
- [ ] The gate passes.

## Required Evidence
- [ ] unittest run of tests/ with all tests passing
- [ ] gate output ending in RESULT: PASS

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user.
- [ ] Anything not covered by an obligation is a spec amendment.
