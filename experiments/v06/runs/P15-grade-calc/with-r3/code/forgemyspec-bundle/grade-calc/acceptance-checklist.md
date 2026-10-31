# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (grade_calc.py) that reads a scores CSV and a weights file, normalizes the weights, computes each student's weighted final grade, letter grade and GPA points, and prints class statistics.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Weights that do not sum to 100 are rescaled so they sum to 100% before grading.
- [ ] Each student gets a weighted final grade, a letter grade and GPA points.
- [ ] Class statistics list mean, median, standard deviation, highest and lowest of the final grades.
- [ ] Malformed input fails with exit code 2 and a clear message.

## Required Evidence
- [ ] Output of the unittest run in tests/ showing every boundary test passing.
- [ ] Command output of grade_calc.py on a sample scores CSV and weights file whose weights sum to 80.
- [ ] Gate report ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If the user wants a different grade scale, standard deviation type or file format, stop and amend the spec before coding.
- [ ] If a test fails, fix grade_calc.py, never the test, unless the spec is amended.
