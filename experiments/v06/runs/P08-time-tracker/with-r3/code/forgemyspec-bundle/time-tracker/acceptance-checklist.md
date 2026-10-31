# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (time_tracker.py) that tracks work sessions per project in a JSON file.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All unittest boundary tests pass.
- [ ] start twice in a row exits non-zero and leaves the file unchanged.
- [ ] report prints one HH:MM:SS total per project.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests passing.
- [ ] Command output of a start, stop, log, report run against a temporary data file.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous or conflicts with another, stop and ask the user.
- [ ] Any behavior not covered by an obligation is a spec amendment.
