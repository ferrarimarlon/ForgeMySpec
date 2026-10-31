# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Grade calculator CLI
- Objective: A single-file, stdlib-only Python CLI (grade_calc.py) that reads a scores CSV and a weights definition, normalizes weights, computes each student's weighted final grade, letter grade and GPA points, and prints class statistics.

## Non-Negotiable Guardrails
- Single file grade_calc.py using only the Python standard library.
- No plus/minus grades, no curving, no dropping of lowest scores, no GUI or file output.
- Missing or non-numeric scores are errors, never silently treated as zero.

## Decision Rules
- If the CSV or weights format is ambiguous in a way the assumptions do not cover, stop and ask the user.
- Do not add features outside the obligations without a spec amendment.

## Success Criteria
- Given a valid scores CSV and weights file, the CLI prints one line per student with final grade, letter and GPA points, then the class statistics.
- Weights that do not sum to 100 produce the same result as the same weights scaled to sum to 100.
- Invalid input exits with status 2 and a message on stderr.

## Assumptions
- Scores CSV has a header row: first column is the student name, remaining columns are assessment names; scores are numbers on a 0-100 scale.
- Weights file is a CSV with header assessment,weight; weights are positive numbers, optionally with a trailing percent sign.
- Letter scale is A >= 90, B >= 80, C >= 70, D >= 60, otherwise F, with GPA points 4.0, 3.0, 2.0, 1.0, 0.0.
- Standard deviation is the population standard deviation.
- Output numbers are rounded to 2 decimals for display; the letter and GPA use the unrounded final grade.

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
