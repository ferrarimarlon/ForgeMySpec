# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python program (organizer.py) that moves files from the top level of a target directory into subdirectories named after their extension, either once (--once) or continuously (--watch), logging every move to organizer.log.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] --once organizes the top level of the target and exits with code 0.
- [ ] --watch keeps organizing files that appear later until interrupted with Ctrl+C.
- [ ] Each move appends one line to organizer.log with a timestamp, source and destination.
- [ ] Hidden files and files in subdirectories are left where they are.

## Required Evidence
- [ ] unittest run of tests/ showing all boundary tests passing
- [ ] gate output ending in RESULT: PASS

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, stop and propose a spec amendment.
- [ ] If the gate fails, fix the implementation, never the approved tests.
