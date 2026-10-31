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
- Single file time_tracker.py with Python standard library only.
- No third-party packages, no database, no network.
- No edit, delete or manual-add subcommands.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- Any behavior beyond the obligations is a spec amendment.

## Success Criteria
- All boundary tests in tests/ pass.
- Starting while a session is active exits non-zero and leaves the file unchanged.

## Assumptions
- The data file path defaults to ~/.time_tracker.json and can be overridden with the --file option or TIME_TRACKER_FILE env var.
- Timestamps are stored as ISO 8601 local-naive strings with seconds precision.
- Overlap means two sessions whose intervals intersect with positive length; an active session counts as ending now.
- Overlaps are detected and reported as warnings in log and report; they are not deleted or merged.
- report counts each project's total as the sum of its session durations, active session included up to now.

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
