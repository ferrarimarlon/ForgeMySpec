# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: State machine CLI
- Objective: Single-file stdlib Python CLI (state_machine.py) that loads a JSON state machine, validates it, runs an event sequence with guards over a context, and prints the transition history.

## Non-Negotiable Guardrails
- Single file state_machine.py, standard library only; no third-party packages.
- No expression evaluator (no eval/exec); guards are structured data only.
- No persistence, no network, no GUI, no hierarchical or parallel states.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- Anything not covered by an obligation is a spec amendment.

## Success Criteria
- A valid definition runs an event sequence and prints the history with exit 0.
- An invalid definition reports every validation error and exits 2.

## Assumptions
- JSON shape: {states: [str], initial: str, final: [str], transitions: [{from, event, to, guard?}]}.
- A guard is an object {key, op, value} with op in ==, !=, <, <=, >, >=, in; it is evaluated against a context dict given by --context JSON.
- Transitions with the same from-state and event are tried in file order; the first whose guard passes (or has no guard) fires.
- An event with no firing transition is rejected: the run stops, the history so far is printed, exit code 1.
- Exit codes: 0 success, 1 rejected event, 2 invalid definition or bad input.
- Final states may still be left by transitions only if declared; running continues until events end or one is rejected.

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
