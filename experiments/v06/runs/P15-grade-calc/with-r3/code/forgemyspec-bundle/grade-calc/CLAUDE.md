# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Grade calculator CLI
- Objective: A single-file, stdlib-only Python CLI (grade_calc.py) that reads a scores CSV and a weights file, normalizes the weights, computes each student's weighted final grade, letter grade and GPA points, and prints class statistics.

## Non-Negotiable Guardrails
- Single file grade_calc.py; Python standard library only, no third-party packages.
- No plus/minus grades, no configurable grade scale, no dropping of lowest scores, no output files or GUI.
- Missing, blank or non-numeric scores are rejected, never treated as zero.

## Decision Rules
- If the user wants a different grade scale, standard deviation type or file format, stop and amend the spec before coding.
- If a test fails, fix grade_calc.py, never the test, unless the spec is amended.

## Success Criteria
- Weights that do not sum to 100 are rescaled so they sum to 100% before grading.
- Each student gets a weighted final grade, a letter grade and GPA points.
- Class statistics list mean, median, standard deviation, highest and lowest of the final grades.
- Malformed input fails with exit code 2 and a clear message.

## Assumptions
- Scores CSV has a header row: first column is the student name, every other column is an assessment; scores are numbers on a 0-100 scale.
- Weights file is a CSV with header assessment,weight; weights are positive numbers (percent or any positive scale).
- Letter scale is fixed without plus/minus: A >= 90 (4.0), B >= 80 (3.0), C >= 70 (2.0), D >= 60 (1.0), else F (0.0), applied to the unrounded final grade.
- Standard deviation is the population standard deviation.
- Invalid input exits with code 2 and a message on stderr; success exits 0.
- Output is plain text on stdout, numbers shown with 2 decimals.

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
