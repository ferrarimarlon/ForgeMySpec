# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Cron expression parser CLI
- Objective: A single-file stdlib-only Python CLI (cron_parser.py) that parses standard 5-field cron expressions, explains them, and computes upcoming run times.

## Non-Negotiable Guardrails
- Single file cron_parser.py, Python standard library only.
- No 6-field (seconds) or 7-field (year) expressions, no @macros, no L/W/# extensions.
- No daemon or scheduler execution; the tool only parses and prints.

## Decision Rules
- If a behavior is not covered by an obligation, treat it as a spec amendment and ask the user.
- Stop and escalate if the day-of-month/day-of-week semantics conflict with the user's expectation.

## Success Criteria
- validate prints a per-field explanation for valid expressions and exits 0.
- validate prints a clear error naming the offending field and exits non-zero for invalid expressions.
- next prints exactly N future run times in ascending order, all matching the expression.
- Expressions that can never fire (such as 0 0 30 2 *) are reported instead of looping forever.

## Assumptions
- Standard 5 fields in order: minute (0-59), hour (0-23), day-of-month (1-31), month (1-12 or JAN-DEC), day-of-week (0-7 or SUN-SAT, 0 and 7 both Sunday).
- When both day-of-month and day-of-week are restricted (not *), a date matches if either matches (Vixie cron semantics); otherwise both must match.
- Run times are computed in the local timezone of the machine, at minute resolution, strictly after now.
- Names are case-insensitive; macros like @daily are not supported.
- Default for -n is 5.

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
