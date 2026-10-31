# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (grade_calc.py) that reads a scores CSV and a weights definition, normalizes weights, computes each student's weighted final grade, letter grade and GPA points, and prints class statistics.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Given a valid scores CSV and weights file, the CLI prints one line per student with final grade, letter and GPA points, then the class statistics.
- [ ] Weights that do not sum to 100 produce the same result as the same weights scaled to sum to 100.
- [ ] Invalid input exits with status 2 and a message on stderr.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all boundary tests passing.
- [ ] Output of the forgemyspec gate for the bundle ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If the CSV or weights format is ambiguous in a way the assumptions do not cover, stop and ask the user.
- [ ] Do not add features outside the obligations without a spec amendment.
