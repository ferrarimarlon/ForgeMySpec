# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Priority Job Scheduler CLI
- Objective: Single-file stdlib Python CLI (scheduler.py) that manages jobs with dependencies and priorities, persisted in scheduler.json.

## Non-Negotiable Guardrails
- Standard library only; no third-party packages.
- All code lives in the single file scheduler.py.
- No daemon, network or real job execution; run-next only simulates execution.
- The ready status is never written to scheduler.json.

## Decision Rules
- Stop and ask if a requirement conflicts with another or cannot be tested.
- Any behavior outside the listed requirements is a spec amendment.

## Success Criteria
- All boundary tests in tests/ pass.
- Every rejected add leaves scheduler.json unchanged.
- A failed job cancels every transitive dependent and no others.

## Assumptions
- CLI shape: python3 scheduler.py add --id ID --name NAME --priority N [--depends-on ID ...]; run-next; fail ID; status; report.
- scheduler.json lives in the current working directory unless SCHEDULER_FILE overrides it (used by tests).
- Validation errors print a message to stderr and exit 1; nothing is persisted on a rejected add.
- fail applies to pending, ready or running jobs; failing an unknown, done, failed or cancelled job is rejected with exit 1.
- run-next with no ready job prints a message and exits 0.
- Ready is derived, never stored; the stored status of a job is pending, running, done, failed or cancelled.
- report lists the execution order (topological, higher priority first among available jobs) and a count per status.
- Name is a non-empty string; depends_on entries are ids, duplicates in the list are collapsed.

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
