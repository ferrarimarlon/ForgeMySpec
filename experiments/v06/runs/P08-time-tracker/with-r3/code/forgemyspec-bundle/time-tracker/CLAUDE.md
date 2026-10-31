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
- Single file time_tracker.py, Python standard library only.
- No manual session editing, no import/export, no GUI or network access.
- No subcommands beyond start, stop, log and report.

## Decision Rules
- If a requirement is ambiguous or conflicts with another, stop and ask the user.
- Any behavior not covered by an obligation is a spec amendment.

## Success Criteria
- All unittest boundary tests pass.
- start twice in a row exits non-zero and leaves the file unchanged.
- report prints one HH:MM:SS total per project.

## Assumptions
- The data file defaults to time_tracker.json in the current directory and can be overridden with --file or the TIME_TRACKER_FILE environment variable.
- Timestamps are stored as ISO 8601 strings in local naive time, second precision.
- Overlap means two sessions whose intervals intersect with positive length; touching endpoints do not overlap.
- Overlaps can only arise from edited or imported data; log reports them and exits 0.
- An active session is counted in log and report up to the current time.

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
