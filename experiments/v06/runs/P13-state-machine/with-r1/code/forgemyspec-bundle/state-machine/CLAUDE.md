# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: State machine CLI
- Objective: Single-file stdlib Python CLI (state_machine.py) that loads a state machine from JSON, validates it, runs a sequence of events with guards on a context, and prints the transition history.

## Non-Negotiable Guardrails
- Single file state_machine.py, stdlib only, no third-party packages.
- No eval or exec of guard expressions.
- No hierarchical states, timers, actions or persistence.

## Decision Rules
- If a requirement is ambiguous (guard syntax, rejection semantics), stop and ask.
- If a test fails, fix the code, never weaken the test.

## Success Criteria
- A valid machine file runs an event sequence and prints the history.
- Every validation defect is reported with the offending name.

## Assumptions
- JSON schema: {states: [str], initial: str, final: [str], transitions: [{from, event, to, guard?}]}.
- A guard is a structured condition {key, op, value} with op in ==, !=, <, <=, >, >=; it is never evaluated with eval.
- Transitions are deterministic: the first transition for the current state and event whose guard passes is taken.
- An event with no enabled transition is rejected, recorded in the history, and leaves the state unchanged.
- Exit codes: 0 success, 1 invalid machine or rejected event, 2 usage or unreadable/malformed JSON.

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
