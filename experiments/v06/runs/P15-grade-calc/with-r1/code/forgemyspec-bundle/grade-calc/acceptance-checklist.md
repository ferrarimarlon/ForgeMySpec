# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (grade_calc.py) that reads a CSV of student scores and a weights definition, normalizes the weights, and prints each student's weighted final grade, letter grade and GPA points, plus class statistics.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Weights that do not sum to 100 produce the same grades as the same weights scaled to sum to 100.
- [ ] Each student's output line shows final grade, letter and GPA points.
- [ ] Class statistics show mean, median, standard deviation, highest and lowest of the final grades.
- [ ] Malformed input exits 2 with a message that names the problem and the CSV line.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests passing.
- [ ] Output of python3 grade_calc.py on a sample scores file and weights file showing grades and statistics.

## Decision Rules Compliance
- [ ] If a requirement cannot be met without a non-stdlib dependency, stop and ask.
- [ ] If a scale or format choice differs from the assumptions, amend the spec before changing code.
