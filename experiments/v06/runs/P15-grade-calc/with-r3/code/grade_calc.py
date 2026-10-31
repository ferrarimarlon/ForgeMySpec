#!/usr/bin/env python3
"""Grade calculator CLI (stdlib only).

Usage: grade_calc.py <scores.csv> <weights.csv>

scores.csv   header: student,<assessment>,...  scores 0-100
weights.csv  header: assessment,weight         positive numbers, any scale
Invalid input exits 2 with a message on stderr.
"""
import csv
import math
import statistics
import sys

SCALE = ((90, "A", 4.0), (80, "B", 3.0), (70, "C", 2.0), (60, "D", 1.0))


class InputError(Exception):
    pass


def _rows(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return [(n, r) for n, r in enumerate(csv.reader(fh), 1)
                    if any(c.strip() for c in r)]
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {path}: {exc}")


def _number(text, where):
    text = text.strip()
    if not text:
        raise InputError(f"{where}: blank value")
    try:
        value = float(text)
    except ValueError:
        raise InputError(f"{where}: not a number: {text!r}")
    if not math.isfinite(value):
        raise InputError(f"{where}: not a finite number: {text!r}")
    return value


def read_weights(path):
    rows = _rows(path)
    if not rows or [c.strip().lower() for c in rows[0][1]] != ["assessment", "weight"]:
        raise InputError(f"{path}: header must be 'assessment,weight'")
    weights = {}
    for n, r in rows[1:]:
        if len(r) != 2 or not r[0].strip():
            raise InputError(f"{path} line {n}: expected 'assessment,weight'")
        name = r[0].strip()
        if name in weights:
            raise InputError(f"{path} line {n}: duplicate assessment {name!r}")
        w = _number(r[1], f"{path} line {n}")
        if w <= 0:
            raise InputError(f"{path} line {n}: weight must be positive")
        weights[name] = w
    if not weights:
        raise InputError(f"{path}: no weights defined")
    return weights


def normalize(weights):
    """Scale weights so they sum to 100 (percent)."""
    total = sum(weights.values())
    if total <= 0:
        raise InputError("weights total must be positive")
    return {k: v / total * 100.0 for k, v in weights.items()}


def read_scores(path, weights):
    rows = _rows(path)
    if not rows:
        raise InputError(f"{path}: empty file")
    header = [c.strip() for c in rows[0][1]]
    if len(header) < 2 or header[0].lower() != "student":
        raise InputError(f"{path}: header must start with 'student'")
    assessments = header[1:]
    if len(set(assessments)) != len(assessments):
        raise InputError(f"{path}: duplicate assessment column")
    for a in assessments:
        if a not in weights:
            raise InputError(f"{path}: assessment {a!r} has no weight")
    for a in weights:
        if a not in assessments:
            raise InputError(f"{path}: weighted assessment {a!r} missing from scores")
    students = []
    for n, r in rows[1:]:
        if len(r) != len(header):
            raise InputError(f"{path} line {n}: expected {len(header)} columns, got {len(r)}")
        name = r[0].strip()
        if not name:
            raise InputError(f"{path} line {n}: blank student name")
        scores = {}
        for a, cell in zip(assessments, r[1:]):
            s = _number(cell, f"{path} line {n} ({a})")
            if not 0 <= s <= 100:
                raise InputError(f"{path} line {n} ({a}): score {s:g} outside 0-100")
            scores[a] = s
        students.append((name, scores))
    if not students:
        raise InputError(f"{path}: no students")
    return students


def final_grade(scores, normalized):
    return sum(scores[a] * w / 100.0 for a, w in normalized.items())


def letter_gpa(grade):
    for threshold, letter, gpa in SCALE:
        if grade >= threshold - 1e-9:
            return letter, gpa
    return "F", 0.0


def class_stats(grades):
    return {
        "mean": statistics.fmean(grades),
        "median": statistics.median(grades),
        "stddev": statistics.pstdev(grades),
        "highest": max(grades),
        "lowest": min(grades),
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: grade_calc.py <scores.csv> <weights.csv>", file=sys.stderr)
        return 2
    try:
        weights = normalize(read_weights(argv[1]))
        students = read_scores(argv[0], weights)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    grades = []
    lines = []
    for name, scores in students:
        g = final_grade(scores, weights)
        letter, gpa = letter_gpa(g)
        grades.append(g)
        lines.append(f"{name}: final {g:.2f} grade {letter} GPA {gpa:.1f}")
    stats = class_stats(grades)
    print("\n".join(lines))
    print("Class statistics")
    for key in ("mean", "median", "stddev", "highest", "lowest"):
        print(f"  {key}: {stats[key]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
