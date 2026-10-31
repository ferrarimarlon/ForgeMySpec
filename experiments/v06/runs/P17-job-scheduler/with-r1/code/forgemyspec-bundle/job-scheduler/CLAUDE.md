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
- No third-party dependencies; stdlib only.
- Everything lives in the single file scheduler.py.
- The status ready is never written to scheduler.json.
- No daemon, no concurrency, no real job execution, no retry or scheduling by time.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- Anything outside the ten requirements is a spec amendment.

## Success Criteria
- All ten requirements are covered by passing unittest tests.

## Assumptions
- Equal-priority ties in the execution order are broken by id ascending (deterministic).
- CLI add takes the flags --id, --name, --priority and --depends-on (comma separated, optional).
- Rejected commands print an error to stderr, exit 1 and leave scheduler.json unchanged.
- run-next with no ready job prints a message and exits 0.
- fail only accepts a job that is pending or ready; other statuses or unknown ids are rejected.
- Cancelled propagation applies to transitive dependents that are not already done.
- The simulated run marks running then done in one invocation; no real work happens.

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
