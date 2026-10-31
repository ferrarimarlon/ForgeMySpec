# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CLI Task Manager
- Objective: A single-file Python CLI (task_manager.py) that manages tasks with CRUD, filtering and done-marking, persisted in SQLite via raw sqlite3 and printed as a terminal table.

## Non-Negotiable Guardrails
- No ORM and no third-party packages; only the Python standard library.
- All code lives in the single file task_manager.py; tests are separate.
- SQL uses parameterized queries, never string-formatted values.
- No web UI, no authentication, no sync, no recurring tasks, no tags or subtasks.

## Decision Rules
- If a requirement is ambiguous (for example due_date format), stop and ask the user before changing the spec.
- Anything outside the obligations is a spec amendment, not an implementation choice.
- Stop if a gate stage fails and fix the cause; never weaken tests.

## Success Criteria
- add, list, update, delete and done commands work end to end against a real SQLite file.
- list --status and --priority return only matching tasks.
- list prints an aligned table with a header row.
- Tasks survive across separate invocations.

## Assumptions
- Database path defaults to tasks.db in the current directory and can be overridden with --db or the TASK_DB environment variable.
- due_date is optional and is an ISO date YYYY-MM-DD; description is optional (empty by default).
- Default priority is medium and default status is todo on add.
- id is an auto-incrementing integer assigned by SQLite.
- Filters combine with AND; list is ordered by id.
- Invalid input or unknown id prints an error to stderr and exits with code 1 (argparse usage errors exit 2).

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- (record stable architecture or policy decisions here)

## Known Pitfalls
- (record recurring implementation failure modes here)
