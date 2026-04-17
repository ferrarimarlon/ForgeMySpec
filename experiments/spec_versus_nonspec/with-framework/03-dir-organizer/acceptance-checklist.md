# Acceptance Checklist — Directory Organizer

## Scope
- [x] Only organizer.py produced.
- [x] No external imports (pathlib, shutil, logging, time, argparse only).
- [x] Both --once and --watch modes implemented.

## Skip Rules
- [x] Hidden files not moved (.hidden_file stays at root).
- [x] Files in subdirs not re-moved (idempotency: 0 moves on second run).
- [x] organizer.log not moved (stays at testdir/organizer.log).

## Extension Routing
- [x] .jpg → images/
- [x] .pdf → documents/
- [x] .mp4 → videos/
- [x] .mp3 → audio/
- [x] .zip → archives/
- [x] .unknown → other/

## Logging
- [x] organizer.log created in target dir.
- [x] Each moved file gets one log entry with correct format.
- [x] "Done. N file(s) moved." summary line present.

## Idempotency
- [x] Second --once run: 0 files moved (all already in subdirs).

## Required Evidence
- [x] Shell session: 6 files → --once → all in correct subdirs.
- [x] cat organizer.log: 6 INFO entries + Done.
- [x] .hidden_file NOT moved.

## Issues Found During Implementation
- None. First run passed all checks.
