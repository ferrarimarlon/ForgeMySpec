# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python program organizer.py that moves the files sitting directly in a target directory into subdirectories named after their extension, once (--once) or continuously (--watch), logging every move to organizer.log.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Running --once on a directory with mixed files leaves each top-level file in its extension subdirectory.
- [ ] Every move appends one line to organizer.log naming source and destination.
- [ ] --watch organizes files that appear after it starts.
- [ ] Hidden files and files already in subdirectories stay where they are.

## Required Evidence
- [ ] Output of the unittest run in tests showing all boundary tests passing.
- [ ] Output of the gate command ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, stop and request a spec amendment.
- [ ] If a test fails, fix organizer.py, never weaken the test.
