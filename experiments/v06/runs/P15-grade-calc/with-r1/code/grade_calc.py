#!/usr/bin/env python3
"""Grade calculator: weighted final grades, letters, GPA points and class statistics."""
import csv
import math
import statistics
import sys


class InputError(Exception):
    pass


def letter_and_gpa(grade):
    for cutoff, letter, gpa in ((90, "A", 4.0), (80, "B", 3.0), (70, "C", 2.0), (60, "D", 1.0)):
        if grade >= cutoff:
            return letter, gpa
    return "F", 0.0


def read_rows(path):
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.reader(f))
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read {path}: {getattr(e, 'strerror', None) or e}")


def parse_number(text, where):
    try:
        v = float(text.strip())
    except ValueError:
        raise InputError(f"{where}: not a number: {text!r}")
    if not math.isfinite(v):
        raise InputError(f"{where}: not a finite number: {text!r}")
    return v


def load_weights(path):
    rows = read_rows(path)
    if not rows or [c.strip().lower() for c in rows[0]] != ["assessment", "weight"]:
        raise InputError(f"{path}: line 1: header must be assessment,weight")
    weights = {}
    for n, row in enumerate(rows[1:], start=2):
        if not row or not any(c.strip() for c in row):
            continue
        if len(row) != 2:
            raise InputError(f"{path}: line {n}: expected 2 columns")
        name = row[0].strip()
        if not name:
            raise InputError(f"{path}: line {n}: empty assessment name")
        if name in weights:
            raise InputError(f"{path}: line {n}: duplicate assessment {name!r}")
        w = parse_number(row[1], f"{path}: line {n}")
        if w < 0:
            raise InputError(f"{path}: line {n}: negative weight")
        weights[name] = w
    total = sum(weights.values())
    if not weights or total <= 0 or not math.isfinite(total):
        raise InputError(f"{path}: weights must have a positive total")
    return {k: v / total for k, v in weights.items()}


def load_scores(path, weights):
    rows = read_rows(path)
    if not rows or len(rows[0]) < 2:
        raise InputError(f"{path}: line 1: header needs a student column and assessments")
    header = [c.strip() for c in rows[0]]
    cols = {}
    for name in weights:
        if name not in header[1:]:
            raise InputError(f"{path}: weighted assessment {name!r} missing from scores")
        cols[name] = header.index(name)
    students = []
    for n, row in enumerate(rows[1:], start=2):
        if not row or not any(c.strip() for c in row):
            continue
        if len(row) != len(header):
            raise InputError(f"{path}: line {n}: expected {len(header)} columns, got {len(row)}")
        student = row[0].strip()
        if not student:
            raise InputError(f"{path}: line {n}: empty student name")
        scores = {}
        for name, i in cols.items():
            where = f"{path}: line {n}, {name}"
            if not row[i].strip():
                raise InputError(f"{where}: blank score")
            s = parse_number(row[i], where)
            if not 0 <= s <= 100:
                raise InputError(f"{where}: score {s:g} out of range 0-100")
            scores[name] = s
        students.append((student, scores))
    if not students:
        raise InputError(f"{path}: no students")
    return students


def final_grade(scores, weights):
    return round(sum(scores[k] * w for k, w in weights.items()), 2)


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
        print("usage: grade_calc.py SCORES.csv WEIGHTS.csv", file=sys.stderr)
        return 2
    try:
        weights = load_weights(argv[1])
        students = load_scores(argv[0], weights)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    grades = []
    print(f"{'Student':<20} {'Final':>7}  Letter  GPA")
    for name, scores in students:
        g = final_grade(scores, weights)
        letter, gpa = letter_and_gpa(g)
        grades.append(g)
        print(f"{name:<20} {g:>7.2f}  {letter:<6}  {gpa:.1f}")
    st = class_stats(grades)
    print("\nClass statistics")
    for k in ("mean", "median", "stddev", "highest", "lowest"):
        print(f"{k:<8} {st[k]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
