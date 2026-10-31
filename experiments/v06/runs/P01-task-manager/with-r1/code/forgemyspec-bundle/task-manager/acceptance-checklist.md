# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python CLI (task_manager.py) that manages tasks with CRUD, filtering and done-marking, persisted in SQLite via raw sqlite3 and printed as terminal tables.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Every CRUD command works against a real SQLite file.
- [ ] Filters by status and priority return only matching tasks.
- [ ] The list command prints an aligned table with a header.

## Required Evidence
- [ ] unittest run output of tests/ with all tests passing
- [ ] gate report showing RESULT: PASS

## Decision Rules Compliance
- [ ] If a requirement cannot be met with the standard library alone, stop and ask the user.
- [ ] Anything outside the listed commands is a spec amendment.
