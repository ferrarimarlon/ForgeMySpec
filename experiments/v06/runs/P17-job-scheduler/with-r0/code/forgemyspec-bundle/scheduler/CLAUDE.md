# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Priority Job Scheduler CLI
- Objective: A single-file, stdlib-only Python CLI (scheduler.py) that manages jobs with dependencies and priorities, persisted in scheduler.json.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- Single source file scheduler.py; no web server, no daemon, no real job execution.
- No retries, scheduling by time, or concurrency.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- If a test fails, fix scheduler.py; never weaken the tests.

## Success Criteria
- Every obligation test passes.
- scheduler.json never contains the status ready.

## Assumptions
- Job id matches ^[A-Za-z0-9_]{1,32}$.
- Priority is an integer from 1 to 10 inclusive.
- add takes --id, --name, --priority and optional --depends-on (comma-separated ids).
- Errors print a message to stderr and exit with code 1; success exits 0.
- run-next simulates execution: the job is set to running, then done, in one invocation, and its id is printed.
- The execution order shown by report is a topological order of all jobs, ties broken by higher priority, then by id ascending.
- fail <id> applies to a job that exists and is not already done, failed or cancelled; otherwise it is rejected with exit 1.
- Status ready is displayed by status and report but never written to scheduler.json.

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
