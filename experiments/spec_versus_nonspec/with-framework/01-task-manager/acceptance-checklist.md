# Acceptance Checklist — CLI Task Manager

## Scope
- [x] Only task_manager.py produced (no other source files).
- [x] No external imports (only sqlite3, argparse, os, sys).
- [x] All 5 subcommands present: add, list, update, delete, done.

## Functional
- [x] `add` creates a task and prints confirmation with assigned id.
- [x] `list` renders aligned table.
- [x] `list --status in-progress` filters by status.
- [x] `list --priority high` filters by priority (argparse choices enforced).
- [x] `update <id> --status in-progress` mutates field.
- [x] `done <id>` sets status=done.
- [x] `delete <id>` removes row and confirms.
- [x] Unknown id → exits 1 with "Task <id> not found".
- [x] Invalid priority → argparse exits 2 with usage message.

## Persistence
- [x] tasks.db created on first run (verified ls -lh: 12K).
- [x] Data survives between invocations.

## Code Quality
- [x] `python3 -c "import task_manager"` exits 0.
- [x] No stray print statements.
- [x] File: 253 lines (< 300).

## Required Evidence
- [x] Shell transcript: add×3, list, list --status, update, done, delete — all recorded above.
- [x] tasks.db: 12K on disk.

## Issues Found During Implementation
- ISSUE-P1-WF-01 | Phase: a5 (validate) | `python` binary not on PATH (macOS uses `python3`).
  Spec context said "Python 3.9+ on PATH" without specifying binary name.
  Fix: ran python3. No code change needed. Low severity.
