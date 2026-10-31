# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python tool (organizer.py) that moves files from the top level of a target directory into subdirectories named after their extension, once (--once) or continuously (--watch), logging every move to organizer.log.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Running --once on a directory with mixed files moves each visible top-level file into its extension subdirectory.
- [ ] Every move appends a line to organizer.log.
- [ ] Hidden files and files already in subdirectories are left in place.

## Required Evidence
- [ ] unittest run of tests/ showing all tests passing
- [ ] Command output of organizer.py --once on a sample directory followed by a directory listing
- [ ] Contents of organizer.log after a run

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, stop and amend the spec instead of adding it.
- [ ] If stdlib cannot do something, escalate to the user; do not add a dependency.
