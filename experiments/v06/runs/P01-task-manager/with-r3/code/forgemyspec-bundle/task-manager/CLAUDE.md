# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: CLI Task Manager
- Objective: A single-file, stdlib-only Python CLI (task_manager.py) that manages tasks with CRUD, filtering, mark-done and table output, persisted in SQLite through raw sqlite3.

## Non-Negotiable Guardrails
- No external dependencies beyond the Python standard library.
- No ORM; only the raw sqlite3 module with parameterized queries.
- Everything lives in the single file task_manager.py; no other module is imported from the project.
- No web UI, no authentication, no multi-user features, no recurring tasks, no tags or subtasks.
- Output is plain text; no colors or third-party table libraries.

## Decision Rules
- If a requirement needs a non-stdlib module, stop and ask the user.
- If behavior is not covered by an obligation, propose a spec amendment instead of adding it.
- Stop and report if any test fails; do not weaken tests to pass.

## Success Criteria
- add, list, update, delete and done all work end to end against a SQLite file.
- list --status and --priority filter correctly, alone and combined.
- Invalid priority, status, date or unknown id exits non-zero with a message on stderr.
- Tasks survive across separate invocations.

## Assumptions
- The database path defaults to tasks.db in the current directory and can be overridden with --db or the TASK_DB environment variable.
- due_date is optional and uses ISO format YYYY-MM-DD; invalid dates are rejected.
- Default priority is medium and default status is todo when not given.
- Subcommands are add, list, update, delete, done, with argparse.
- Title is required and non-empty; description is optional.
- Python 3.8+ stdlib only.

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
