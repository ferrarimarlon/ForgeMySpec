# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Time tracker CLI
- Objective: A single-file, stdlib-only Python CLI (time_tracker.py) that tracks work sessions per project in a JSON file.

## Non-Negotiable Guardrails
- Python standard library only; everything in the single file time_tracker.py.
- No editing or deleting sessions, no tags, no export formats, no network.
- Corrupt JSON is never silently overwritten.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- Anything not covered by an obligation is a spec amendment.

## Success Criteria
- All subcommands behave as specified in the boundary tests.
- The gate passes.

## Assumptions
- Data file path comes from --file, else env TIME_TRACKER_FILE, else ./time_tracker.json.
- Timestamps are stored as ISO 8601 strings in UTC; the active session has end null.
- Two sessions overlap when each starts before the other ends; an active session ends 'now' for this check.
- start never creates an overlap by itself; overlaps are detected in log and report from existing data (e.g. hand-edited file).
- Exit code 0 on success, 1 on a refused operation, 2 on a corrupt data file or bad usage.

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
