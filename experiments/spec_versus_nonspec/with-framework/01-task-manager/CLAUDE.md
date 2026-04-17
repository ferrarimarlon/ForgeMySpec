# CLAUDE.md — CLI Task Manager

## Role
Implement task_manager.py strictly from spec.yaml. No deviations from scope_contract.

## Non-Negotiable Guardrails
- Single file: task_manager.py only.
- stdlib only — no pip installs.
- Subcommands exactly: add, list, update, delete, done.
- DB file: tasks.db in cwd.
- Task fields: id, title, description, priority, status, due_date.

## Decision Rules (from spec)
- Missing due_date → store "" → display "-".
- Invalid priority/status → exit 1 with usage message.
- Task id not found → print "Task <id> not found" → exit 1.
- Table column widths: ID(4) | Title(30) | Priority(8) | Status(11) | Due(12).
- `description` stored in DB, not shown in list table.

## Known Pitfalls
- argparse `add_subparsers` requires `dest` param in Python 3.9+ to avoid ambiguous subcommand errors.
- sqlite3 `executemany` not needed; single-row inserts suffice.
- `ljust`/`rjust` truncate long titles: always slice to max width before padding.
- Avoid `print(f"{var!r}")` in table — use str() explicitly.
