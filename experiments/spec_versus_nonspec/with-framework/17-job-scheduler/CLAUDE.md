# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Priority Job Scheduler with Dependency Graph
- Objective: A single-file Python CLI (scheduler.py) that manages jobs with dependency relationships, detects cycles, computes execution order via topological sort with priority tiebreak, propagates failures recursively, and persists state to a JSON file.

## Non-Negotiable Guardrails
- A job is ready when status=pending AND every job in depends_on has status=done.
- ready is recomputed on every load; it is never persisted as a stored status.
- run-next transitions the chosen job directly from ready to done (no intermediate pause in running state visible to user).
- No eval(), no subprocess, no external libraries.

## Decision Rules
- Cycle check must run BEFORE writing to scheduler.json — never persist a cyclic graph.
- recompute_ready must run after every state change (add, run-next, fail) before save.
- ready is never written to scheduler.json — always recomputed on load.
- propagate_failure must use BFS/DFS to find ALL transitive dependents, not just direct children.
- If a job is already failed/cancelled/done, fail command should print an error and exit 1.
- Priority tiebreak in run-next: higher number wins. If equal, any order is acceptable.

## Success Criteria
- After any add or run-next, ready status is recomputed correctly for all pending jobs.
- run-next picks the highest-priority ready job; prints its id before marking done.
- fail <id> sets target to failed and recursively sets all transitive dependents to cancelled.
- status prints a table with columns id, name, priority, status, depends_on.
- report prints counts per status (only statuses with count > 0).
- Cycle in the dependency graph is detected and rejected with a clear error message.

## Assumptions
- scheduler.json may not exist on first run; create on first add.
- ready status is never stored; it is recomputed on every load from scratch.
- All status transitions are explicit; no implicit state changes.
- run-next is a simulation; it does not execute actual subprocesses.

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
