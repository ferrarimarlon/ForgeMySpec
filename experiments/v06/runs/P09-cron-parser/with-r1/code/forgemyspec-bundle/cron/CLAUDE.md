# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Cron expression parser CLI
- Objective: A single-file, stdlib-only Python CLI (cron_parser.py) that validates standard 5-field cron expressions and prints upcoming run times.

## Non-Negotiable Guardrails
- Single file cron_parser.py, standard library only; no third-party packages.
- No support for 6/7-field expressions, seconds, @aliases (@daily), or the L, W, # and ? extensions.
- No daemon, scheduling, or command execution; the tool only parses and prints.

## Decision Rules
- If a requirement conflicts with standard cron behavior, stop and ask before choosing.
- Anything outside the obligations is a spec amendment.

## Success Criteria
- validate prints a per-field explanation for a valid expression and an error naming the field for an invalid one.
- next prints N future run times, in ascending order, each matching the expression.
- Impossible dates such as February 30 never appear in the output.

## Assumptions
- Expression is passed as one quoted argument; fields are separated by whitespace.
- Times are local naive time; the next run is strictly after the current minute, with second 0.
- When both day-of-month and day-of-week are restricted (not *), a date matches if either matches (Vixie cron semantics).
- Day-of-week accepts 0-7 where 0 and 7 are Sunday; names are 3-letter, case-insensitive (JAN-DEC, SUN-SAT).
- Step forms are */n, a-b/n and a/n (a through the field maximum); n must be at least 1.
- An expression that can never match any date (for example 0 0 30 2 *) is reported as an error, searching up to 8 years ahead.
- Exit codes: 0 success, 1 invalid expression or never-matching, 2 usage error.

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
