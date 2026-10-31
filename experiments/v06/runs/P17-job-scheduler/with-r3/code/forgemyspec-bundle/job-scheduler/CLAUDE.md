# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Priority Job Scheduler CLI
- Objective: A single-file, stdlib-only Python CLI (scheduler.py) that manages jobs with priorities and dependencies, persists them in scheduler.json and executes them in dependency order with priority tiebreak.

## Non-Negotiable Guardrails
- Single file scheduler.py using only the Python standard library.
- The status ready is never written to scheduler.json.
- No real job execution, no concurrency, no network, no removal or editing of jobs.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- Anything outside the obligations is a spec amendment.

## Success Criteria
- All boundary tests pass.
- Every rule of the request is covered by an obligation.

## Assumptions
- Job ids match ^[A-Za-z0-9_]{1,32}$ and are case-sensitive.
- Priority is an integer 1-10 (bool and non-integers rejected).
- scheduler.json lives in the current working directory, overridable by a --file option.
- Invalid input exits with code 1 and a message on stderr; success exits 0.
- run-next simulates execution: it marks the job running, then done, in one invocation.
- fail <id> applies to a pending, ready or running job; an unknown id or a job already done, failed or cancelled is an error.
- A job whose dependency is failed or cancelled is cancelled; cancelled jobs never become ready.
- Adding a job that depends on a failed or cancelled job is allowed and the new job is created cancelled.
- report prints per-status counts and the execution order of non-terminal jobs.

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
