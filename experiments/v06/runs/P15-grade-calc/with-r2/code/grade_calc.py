#!/usr/bin/env python3
"""Grade calculator CLI.

Usage: grade_calc.py SCORES.csv WEIGHTS.csv

SCORES.csv:  header row "student,<assessment>,..."; scores are numbers 0-100.
WEIGHTS.csv: header "assessment,weight"; weights are positive numbers
             (a trailing % is allowed) and are normalized to sum to 100.
"""
import csv
import math
import sys

SCALE = [(90.0, "A", 4.0), (80.0, "B", 3.0), (70.0, "C", 2.0), (60.0, "D", 1.0)]


class InputError(Exception):
    pass


def _read_rows(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return list(csv.reader(fh))
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("cannot read %s: %s" % (path, exc))


def _number(text, what):
    t = text.strip()
    if t.endswith("%"):
        t = t[:-1].strip()
    try:
        value = float(t)
    except ValueError:
        raise InputError("%s is not a number: %r" % (what, text))
    if not math.isfinite(value):
        raise InputError("%s is not a finite number: %r" % (what, text))
    return value


def parse_weights(path):
    rows = [r for r in _read_rows(path) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise InputError("%s: no weights found" % path)
    weights = {}
    for row in rows[1:]:
        if len(row) < 2 or not row[0].strip():
            raise InputError("%s: malformed weight row %r" % (path, row))
        name = row[0].strip()
        if name in weights:
            raise InputError("%s: duplicate assessment %r" % (path, name))
        w = _number(row[1], "weight for %r" % name)
        if w <= 0:
            raise InputError("weight for %r must be positive" % name)
        weights[name] = w
    return weights


def normalize_weights(weights):
    """Scale weights so they sum to 100."""
    total = sum(weights.values())
    return {k: v * 100.0 / total for k, v in weights.items()}


def parse_scores(path, weights):
    rows = [r for r in _read_rows(path) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise InputError("%s: no students found" % path)
    header = [c.strip() for c in rows[0]]
    assessments = header[1:]
    if not assessments:
        raise InputError("%s: no assessment columns" % path)
    if len(set(assessments)) != len(assessments):
        raise InputError("%s: duplicate assessment column" % path)
    for a in assessments:
        if a not in weights:
            raise InputError("assessment %r has no weight" % a)
    for w in weights:
        if w not in assessments:
            raise InputError("weight given for %r but it has no score column" % w)
    students = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            raise InputError("%s: row %d has %d fields, expected %d"
                             % (path, i, len(row), len(header)))
        name = row[0].strip()
        if not name:
            raise InputError("%s: row %d has no student name" % (path, i))
        scores = {}
        for a, cell in zip(assessments, row[1:]):
            if not cell.strip():
                raise InputError("%s: %s is missing a score for %r" % (path, name, a))
            scores[a] = _number(cell, "score of %s for %r" % (name, a))
            if not 0.0 <= scores[a] <= 100.0:
                raise InputError("%s: score of %s for %r out of range 0-100"
                                 % (path, name, a))
        students.append((name, scores))
    return students


def final_grade(scores, normalized):
    return sum(scores[a] * w / 100.0 for a, w in normalized.items())


def letter_and_gpa(grade):
    for threshold, letter, gpa in SCALE:
        if grade >= threshold:
            return letter, gpa
    return "F", 0.0


def class_stats(grades):
    n = len(grades)
    mean = sum(grades) / n
    ordered = sorted(grades)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    std = math.sqrt(sum((g - mean) ** 2 for g in grades) / n)
    return {"mean": mean, "median": median, "std dev": std,
            "highest": ordered[-1], "lowest": ordered[0]}


def run(scores_path, weights_path, out):
    weights = parse_weights(weights_path)
    students = parse_scores(scores_path, weights)
    normalized = normalize_weights(weights)
    grades = []
    out.write("%-20s %8s %7s %5s\n" % ("Student", "Final", "Letter", "GPA"))
    for name, scores in students:
        g = final_grade(scores, normalized)
        letter, gpa = letter_and_gpa(g)
        grades.append(g)
        out.write("%-20s %8.2f %7s %5.1f\n" % (name, g, letter, gpa))
    out.write("\nClass statistics (%d students)\n" % len(grades))
    for key, value in class_stats(grades).items():
        out.write("%-10s %.2f\n" % (key, value))


def main(argv=None, out=None, err=None):
    argv = sys.argv[1:] if argv is None else argv
    out = out or sys.stdout
    err = err or sys.stderr
    if len(argv) != 2:
        err.write("usage: grade_calc.py SCORES.csv WEIGHTS.csv\n")
        return 2
    try:
        run(argv[0], argv[1], out)
    except InputError as exc:
        err.write("error: %s\n" % exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
