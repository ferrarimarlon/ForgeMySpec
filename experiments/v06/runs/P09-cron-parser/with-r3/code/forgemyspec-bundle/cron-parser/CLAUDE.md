# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Cron expression parser CLI
- Objective: A single-file, stdlib-only Python CLI (cron_parser.py) that parses standard 5-field cron expressions, explains them with validate, and prints upcoming run times with next.

## Non-Negotiable Guardrails
- Standard library only; everything lives in the single file cron_parser.py.
- No macros (@daily), no seconds field, no year field, no L/W/# extensions, no timezone options.
- Invalid input exits with status 2 and a message on stderr; it never raises a traceback.

## Decision Rules
- Stop and ask if a requirement needs anything beyond the standard library or a second file.
- Treat any behavior not covered by an obligation as a spec amendment.

## Success Criteria
- validate prints one explanation line per field for a valid expression and exits 0.
- validate names the field and the reason for an invalid expression and exits 2.
- next prints N future run times, ascending, each matching the expression.
- Impossible dates such as 0 0 30 2 * are reported, never looped on forever.

## Assumptions
- Fields are minute 0-59, hour 0-23, day-of-month 1-31, month 1-12, day-of-week 0-7 (0 and 7 are Sunday).
- When both day-of-month and day-of-week are restricted (not *), a date matches if either matches (Vixie cron semantics).
- Run times are computed in local time, at minute resolution, strictly after now; the search horizon is 8 years.
- A hidden --from 'YYYY-MM-DD HH:MM' option on next replaces now, so tests are deterministic.
- Macros such as @daily and 6-field expressions with seconds are out of scope.

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
