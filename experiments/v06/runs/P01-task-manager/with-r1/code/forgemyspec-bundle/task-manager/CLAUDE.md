# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CLI Task Manager
- Objective: A single-file Python CLI (task_manager.py) that manages tasks with CRUD, filtering and done-marking, persisted in SQLite via raw sqlite3 and printed as terminal tables.

## Non-Negotiable Guardrails
- No ORM and no third-party packages; only the standard library.
- All code of the CLI lives in the single file task_manager.py.
- No web UI, no authentication, no multi-user features, no import or export.

## Decision Rules
- If a requirement cannot be met with the standard library alone, stop and ask the user.
- Anything outside the listed commands is a spec amendment.

## Success Criteria
- Every CRUD command works against a real SQLite file.
- Filters by status and priority return only matching tasks.
- The list command prints an aligned table with a header.

## Assumptions
- Subcommands: add, list, update, delete, done; database path defaults to tasks.db in the current directory and can be overridden with --db.
- due_date is optional and is an ISO date YYYY-MM-DD; defaults for a new task are priority medium and status todo.
- Invalid input or an unknown task id exits with code 1 and a message on stderr.

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
