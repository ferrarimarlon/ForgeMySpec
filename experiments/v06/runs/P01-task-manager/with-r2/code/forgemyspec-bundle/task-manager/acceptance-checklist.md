# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python CLI (task_manager.py) that manages tasks with CRUD, filtering and done-marking, persisted in SQLite via raw sqlite3 and printed as a terminal table.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] add, list, update, delete and done commands work end to end against a real SQLite file.
- [ ] list --status and --priority return only matching tasks.
- [ ] list prints an aligned table with a header row.
- [ ] Tasks survive across separate invocations.

## Required Evidence
- [ ] Output of python3 -m unittest discover tests showing all boundary tests passing.
- [ ] Output of the gate command ending in RESULT: PASS.
- [ ] Sample CLI session output showing add, list with filters, update, done and delete.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous (for example due_date format), stop and ask the user before changing the spec.
- [ ] Anything outside the obligations is a spec amendment, not an implementation choice.
- [ ] Stop if a gate stage fails and fix the cause; never weaken tests.
