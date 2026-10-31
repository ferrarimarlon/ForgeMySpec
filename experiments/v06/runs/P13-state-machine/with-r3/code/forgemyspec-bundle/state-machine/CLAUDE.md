# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: State machine CLI
- Objective: A single-file, stdlib-only Python CLI (state_machine.py) that loads a state machine definition from JSON, validates it, runs a sequence of events with guards evaluated on a context, and prints the history of transitions.

## Non-Negotiable Guardrails
- Single file state_machine.py, Python standard library only.
- No eval or exec of guard text.
- No persistence, no network, no context mutation by transitions, no actions or hooks on transitions.

## Decision Rules
- If a requirement needs behavior outside the obligations, stop and amend the spec.
- Stop and ask when guard semantics or exit codes conflict with the request.

## Success Criteria
- A valid definition runs an event sequence and prints each transition as from, event, to.
- Invalid definitions are reported with all problems and exit 2.
- All boundary tests pass.

## Assumptions
- Definition JSON keys: states (list of names), initial (name), finals (list of names), transitions (list of objects with from, event, to and optional guard).
- A guard is an object with key, op and value (or a list of them, all must hold), with op in ==, !=, <, <=, >, >=, in; evaluated on the context dict without eval.
- A missing context key makes a guard false.
- When several transitions from the current state match the event, the first one in definition order whose guard holds is taken.
- An event with no enabled transition is rejected: the run stops, the rejection is reported, and the exit code is 1.
- Exit codes: 0 success, 1 rejected event, 2 invalid definition or bad input.
- Context is given as JSON via --context (default empty object); events are positional arguments after the definition file; transitions never modify the context.
- Unreachable means not reachable from the initial state following transitions, ignoring guards.

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
