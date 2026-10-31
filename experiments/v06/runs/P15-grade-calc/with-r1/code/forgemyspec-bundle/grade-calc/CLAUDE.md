# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Grade calculator CLI
- Objective: A single-file, stdlib-only Python CLI (grade_calc.py) that reads a CSV of student scores and a weights definition, normalizes the weights, and prints each student's weighted final grade, letter grade and GPA points, plus class statistics.

## Non-Negotiable Guardrails
- Python standard library only; one source file named grade_calc.py.
- No GUI, no web service, no file output: results go to stdout.
- No +/- letter grades and no configurable grading scale.
- Missing, blank, non-numeric or out-of-range scores are rejected, never silently treated as zero.

## Decision Rules
- If a requirement cannot be met without a non-stdlib dependency, stop and ask.
- If a scale or format choice differs from the assumptions, amend the spec before changing code.

## Success Criteria
- Weights that do not sum to 100 produce the same grades as the same weights scaled to sum to 100.
- Each student's output line shows final grade, letter and GPA points.
- Class statistics show mean, median, standard deviation, highest and lowest of the final grades.
- Malformed input exits 2 with a message that names the problem and the CSV line.

## Assumptions
- Scores CSV has a header row; the first column is the student name and every other column is an assessment, with scores from 0 to 100.
- Weights file is a CSV with header assessment,weight; weights are non-negative numbers, not necessarily percentages.
- Normalization divides each weight by the weight total, so the normalized weights sum to 1 (100%).
- Letter scale: A >= 90, B >= 80, C >= 70, D >= 60, otherwise F. GPA points: A 4.0, B 3.0, C 2.0, D 1.0, F 0.0. The final grade is rounded to 2 decimals before the letter is chosen.
- Standard deviation is the population standard deviation (statistics.pstdev).
- Assessment columns that have no weight are ignored; a weighted assessment missing from the scores CSV is an error.
- Usage: python3 grade_calc.py SCORES.csv WEIGHTS.csv; errors go to stderr with exit code 2, success exits 0.

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
