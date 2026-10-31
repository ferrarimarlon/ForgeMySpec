#!/usr/bin/env python3
"""Grade calculator.

Usage:
    python3 grade_calc.py scores.csv weights.txt [--missing zero|skip] [--population]

scores.csv   header row: a student-name column followed by one column per
             assessment, e.g.  student,homework,midterm,final
weights file either JSON ({"homework": 30, "midterm": 30, "final": 40}) or
             lines of "name,weight" / "name=weight" / "name: weight"
             (a trailing % is allowed; '#' starts a comment).

Weights that do not sum to 100 are normalized to sum to 100%.
Scores are percentages (0-100).
"""

import argparse
import csv
import json
import math
import statistics
import sys

# (minimum percent, letter, GPA points) - standard US 4.0 scale
GRADE_SCALE = [
    (93, "A", 4.0), (90, "A-", 3.7),
    (87, "B+", 3.3), (83, "B", 3.0), (80, "B-", 2.7),
    (77, "C+", 2.3), (73, "C", 2.0), (70, "C-", 1.7),
    (67, "D+", 1.3), (63, "D", 1.0), (60, "D-", 0.7),
    (float("-inf"), "F", 0.0),
]


def parse_number(text, what):
    try:
        value = float(str(text).strip().rstrip("%"))
    except ValueError:
        raise ValueError(f"{what}: {text!r} is not a number")
    if not math.isfinite(value):
        raise ValueError(f"{what}: {text!r} is not a finite number")
    return value


def load_weights(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        text = f.read()
    weights = {}
    if text.lstrip().startswith("{"):
        for name, w in json.loads(text).items():
            weights[name.strip()] = parse_number(w, f"weight for {name!r}")
    else:
        for lineno, line in enumerate(text.splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            for sep in (",", "=", ":"):
                if sep in line:
                    name, _, w = line.rpartition(sep)
                    break
            else:
                raise ValueError(f"{path}:{lineno}: expected 'name,weight'")
            name = name.strip()
            if name.lower() in ("assessment", "name") and w.strip().lower() in ("weight", "percent"):
                continue  # header row
            if name in weights:
                raise ValueError(f"{path}:{lineno}: duplicate weight for {name!r}")
            weights[name] = parse_number(w, f"{path}:{lineno}")
    if not weights:
        raise ValueError(f"{path}: no weights found")
    for name, w in weights.items():
        if w < 0:
            raise ValueError(f"weight for {name!r} is negative")
    if sum(weights.values()) <= 0:
        raise ValueError("weights sum to zero")
    return weights


def normalize_weights(weights):
    """Scale weights so they sum to 100."""
    total = sum(weights.values())
    return {k: v * 100.0 / total for k, v in weights.items()}, total


def load_scores(path, weights):
    """Return list of (student, {assessment: score or None})."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            raise ValueError(f"{path}: empty file")
        if len(header) < 2:
            raise ValueError(f"{path}: need a student column and at least one assessment")
        cols = header[1:]
        missing_cols = [w for w in weights if w not in cols]
        if missing_cols:
            raise ValueError("weighted assessments not in CSV: " + ", ".join(missing_cols))
        extra = [c for c in cols if c not in weights]
        if extra:
            print("note: ignoring columns with no weight: " + ", ".join(extra), file=sys.stderr)
        rows = []
        for lineno, row in enumerate(reader, 2):
            if not any(c.strip() for c in row):
                continue
            if len(row) != len(header):
                raise ValueError(f"{path}:{lineno}: expected {len(header)} fields, got {len(row)}")
            student = row[0].strip()
            if not student:
                raise ValueError(f"{path}:{lineno}: missing student name")
            scores = {}
            for col, cell in zip(cols, row[1:]):
                if col not in weights:
                    continue
                cell = cell.strip()
                if cell == "" or cell.upper() in ("NA", "N/A"):
                    scores[col] = None
                else:
                    scores[col] = parse_number(cell, f"{path}:{lineno} {col}")
            rows.append((student, scores))
    if not rows:
        raise ValueError(f"{path}: no student rows")
    return rows


def final_grade(scores, norm_weights, missing):
    """Weighted percentage. 'skip' reweights over completed work; 'zero' counts 0.

    Returns None if nothing has been scored (under 'skip').
    """
    num = den = 0.0
    for name, w in norm_weights.items():
        s = scores[name]
        if s is None:
            if missing == "skip":
                continue
            s = 0.0
        num += s * w
        den += w
    return num / den if den > 0 else None


def letter_and_gpa(pct):
    # Round first so the displayed percentage and the letter always agree.
    r = round(pct + 1e-9, 2)
    for floor, letter, gpa in GRADE_SCALE:
        if r >= floor:
            return letter, gpa


def class_stats(values, population):
    stdev = 0.0
    if len(values) > 1:
        stdev = statistics.pstdev(values) if population else statistics.stdev(values)
    return {
        "Mean": statistics.fmean(values),
        "Median": statistics.median(values),
        "Std dev": stdev,
        "Highest": max(values),
        "Lowest": min(values),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Weighted grade calculator")
    p.add_argument("scores", help="CSV: student, then one column per assessment")
    p.add_argument("weights", help="weights file (JSON or name,weight lines)")
    p.add_argument("--missing", choices=("zero", "skip"), default="zero",
                   help="blank scores count as zero (default) or are skipped and "
                        "the remaining weights re-normalized")
    p.add_argument("--population", action="store_true",
                   help="population standard deviation instead of sample")
    args = p.parse_args(argv)

    try:
        raw = load_weights(args.weights)
        norm, total = normalize_weights(raw)
        students = load_scores(args.scores, raw)
    except (OSError, ValueError, json.JSONDecodeError, AttributeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not math.isclose(total, 100.0, abs_tol=1e-9):
        print(f"note: weights sum to {total:g}, normalized to 100%", file=sys.stderr)
    print("Weights:  " + ", ".join(f"{k} {v:.2f}%" for k, v in norm.items()))
    print()

    results = []
    for name, scores in students:
        pct = final_grade(scores, norm, args.missing)
        results.append((name, pct))

    width = max(len("Student"), *(len(n) for n, _ in results))
    print(f"{'Student':<{width}}  {'Final %':>8}  {'Letter':^6}  {'GPA':>4}")
    print(f"{'-' * width}  {'-' * 8}  {'-' * 6}  {'-' * 4}")
    graded = []
    for name, pct in results:
        if pct is None:
            print(f"{name:<{width}}  {'n/a':>8}  {'-':^6}  {'-':>4}")
            continue
        letter, gpa = letter_and_gpa(pct)
        graded.append(pct)
        print(f"{name:<{width}}  {pct:8.2f}  {letter:^6}  {gpa:4.1f}")

    print()
    if not graded:
        print("No gradable students; no statistics.")
        return 0
    print(f"Class statistics (n={len(graded)}"
          f"{', population' if args.population else ''} std dev):")
    for label, value in class_stats(graded, args.population).items():
        print(f"  {label:<8} {value:7.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
