# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (task_manager.py) that manages tasks with CRUD, filtering, mark-done and table output, persisted in SQLite through raw sqlite3.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] add, list, update, delete and done all work end to end against a SQLite file.
- [ ] list --status and --priority filter correctly, alone and combined.
- [ ] Invalid priority, status, date or unknown id exits non-zero with a message on stderr.
- [ ] Tasks survive across separate invocations.

## Required Evidence
- [ ] unittest run output showing all boundary tests in tests/ pass
- [ ] gate report ending with RESULT: PASS
- [ ] sample session output of add, list, update, done and delete against a temporary database

## Decision Rules Compliance
- [ ] If a requirement needs a non-stdlib module, stop and ask the user.
- [ ] If behavior is not covered by an obligation, propose a spec amendment instead of adding it.
- [ ] Stop and report if any test fails; do not weaken tests to pass.
