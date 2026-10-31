#!/usr/bin/env python3
"""Grade calculator.

Reads a CSV of students and assessment scores plus a weights definition,
normalizes the weights to 100%, and prints each student's weighted final
grade, letter grade and GPA points, followed by class statistics.

Scores CSV: first column is the student name/ID, every other column is an
assessment. Scores are numbers on a 0..max-score scale (default 100).

    name,Homework,Midterm,Final
    Alice,95,88,92

Weights: either inline (--weights "Homework=30,Midterm=30,Final=50") or a
file (--weights-file) with one "assessment,weight" or "assessment=weight"
per line. Weights may carry a trailing %. They need not sum to 100; they
are rescaled proportionally.

Usage:
    python3 grade_calc.py scores.csv --weights-file weights.csv
"""

import argparse
import csv
import statistics
import sys

# (minimum percent, letter, GPA points), highest first.
SCALE = [
    (93, "A", 4.0), (90, "A-", 3.7),
    (87, "B+", 3.3), (83, "B", 3.0), (80, "B-", 2.7),
    (77, "C+", 2.3), (73, "C", 2.0), (70, "C-", 1.7),
    (67, "D+", 1.3), (63, "D", 1.0), (60, "D-", 0.7),
    (float("-inf"), "F", 0.0),
]


class GradeError(Exception):
    pass


def parse_number(text, what):
    text = text.strip().rstrip("%").strip()
    try:
        value = float(text)
    except ValueError:
        raise GradeError(f"invalid number for {what}: {text!r}")
    if value != value or value in (float("inf"), float("-inf")):
        raise GradeError(f"invalid number for {what}: {text!r}")
    return value


def parse_weight_pairs(pairs):
    weights = {}
    for raw in pairs:
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        sep = "=" if "=" in raw else ","
        if sep not in raw:
            raise GradeError(f"bad weight entry (expected name=weight): {raw!r}")
        name, _, value = raw.rpartition(sep)
        name = name.strip()
        if not name:
            raise GradeError(f"bad weight entry (empty name): {raw!r}")
        if name in weights:
            raise GradeError(f"duplicate weight for {name!r}")
        weight = parse_number(value, f"weight of {name!r}")
        if weight < 0:
            raise GradeError(f"negative weight for {name!r}")
        weights[name] = weight
    return weights


def load_weights(inline, path):
    pairs = []
    if path:
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                pairs.extend(f.read().splitlines())
        except OSError as e:
            raise GradeError(f"cannot read weights file: {e}")
    if inline:
        pairs.extend(inline.split(","))
        # Inline uses commas as separators, so only "=" form is valid there.
        if any("=" not in p for p in inline.split(",") if p.strip()):
            raise GradeError("inline --weights must look like A=30,B=70")
    weights = parse_weight_pairs(pairs)
    if not weights:
        raise GradeError("no weights provided (use --weights or --weights-file)")
    if sum(weights.values()) <= 0:
        raise GradeError("weights sum to zero")
    return weights


def normalize(weights):
    total = sum(weights.values())
    return {k: v * 100.0 / total for k, v in weights.items()}, total


def load_scores(path, weights, max_score):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except OSError as e:
        raise GradeError(f"cannot read scores file: {e}")
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise GradeError("scores file is empty")
    header = [h.strip() for h in rows[0]]
    columns = header[1:]
    if len(set(columns)) != len(columns):
        raise GradeError("duplicate assessment columns in scores file")
    missing = [w for w in weights if w not in columns]
    if missing:
        raise GradeError("weights reference columns not in CSV: " + ", ".join(missing))
    unweighted = [c for c in columns if c not in weights]
    students = []
    for lineno, row in enumerate(rows[1:], start=2):
        name = row[0].strip()
        if not name:
            raise GradeError(f"row {lineno}: missing student name")
        scores = {}
        for col, cell in zip(columns, row[1:]):
            if col not in weights:
                continue
            if cell.strip() == "":
                scores[col] = None
            else:
                v = parse_number(cell, f"{name} / {col}")
                if v < 0:
                    raise GradeError(f"{name} / {col}: negative score {v}")
                scores[col] = v * 100.0 / max_score
        for col in weights:
            scores.setdefault(col, None)  # short row
        students.append((name, scores))
    if not students:
        raise GradeError("scores file has no students")
    return students, unweighted


def final_grade(scores, norm, skip_missing):
    """Weighted percent. Missing counts as 0 unless skip_missing, in which
    case the weights of the scored assessments are re-normalized."""
    present = {k: w for k, w in norm.items() if scores[k] is not None}
    if skip_missing:
        total = sum(present.values())
        if total <= 0:
            return None
        return sum(scores[k] * w for k, w in present.items()) / total
    return sum(scores[k] * w for k, w in present.items()) / 100.0


def letter_and_gpa(pct):
    rounded = round(pct, 2)  # grade as displayed, avoids 92.999 -> A-
    for floor, letter, gpa in SCALE:
        if rounded >= floor:
            return letter, gpa


def class_stats(values, population):
    n = len(values)
    if n < 2:
        sd = 0.0
    else:
        sd = statistics.pstdev(values) if population else statistics.stdev(values)
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "std dev": sd,
        "highest": max(values),
        "lowest": min(values),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Weighted grade calculator.")
    p.add_argument("scores", help="CSV of student scores")
    p.add_argument("-w", "--weights", help='inline weights, e.g. "HW=30,Exam=70"')
    p.add_argument("-f", "--weights-file", help="file with name,weight lines")
    p.add_argument("--max-score", type=float, default=100.0,
                   help="maximum raw score per assessment (default 100)")
    p.add_argument("--skip-missing", action="store_true",
                   help="re-normalize over scored assessments instead of "
                        "counting blanks as 0")
    p.add_argument("--population", action="store_true",
                   help="population std dev instead of sample")
    args = p.parse_args(argv)

    try:
        if args.max_score <= 0:
            raise GradeError("--max-score must be positive")
        weights = load_weights(args.weights, args.weights_file)
        norm, total = normalize(weights)
        students, unweighted = load_scores(args.scores, weights, args.max_score)
    except GradeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if abs(total - 100.0) > 1e-9:
        print(f"note: weights summed to {total:g}%, normalized to 100%.",
              file=sys.stderr)
    if unweighted:
        print("note: ignoring columns with no weight: " + ", ".join(unweighted),
              file=sys.stderr)

    print("Weights (normalized):")
    for k, w in norm.items():
        print(f"  {k}: {w:.2f}%")
    print()

    results = []
    skipped = []
    for name, scores in students:
        pct = final_grade(scores, norm, args.skip_missing)
        if pct is None:
            skipped.append(name)
            continue
        letter, gpa = letter_and_gpa(pct)
        gaps = sum(1 for v in scores.values() if v is None)
        results.append((name, pct, letter, gpa, gaps))

    if not results:
        print("error: no student has any scores", file=sys.stderr)
        return 1

    width = max(len("Student"), max(len(r[0]) for r in results))
    print(f"{'Student':<{width}}  {'Final %':>8}  {'Grade':>5}  {'GPA':>4}")
    for name, pct, letter, gpa, gaps in results:
        flag = f"  ({gaps} missing)" if gaps else ""
        print(f"{name:<{width}}  {pct:>8.2f}  {letter:>5}  {gpa:>4.1f}{flag}")
    for name in skipped:
        print(f"{name:<{width}}  (no scores, excluded)")

    pcts = [r[1] for r in results]
    gpas = [r[3] for r in results]
    stats = class_stats(pcts, args.population)
    hi = [r[0] for r in results if r[1] == stats["highest"]]
    lo = [r[0] for r in results if r[1] == stats["lowest"]]
    print()
    print(f"Class statistics (n={len(results)}):")
    print(f"  Mean:     {stats['mean']:.2f}")
    print(f"  Median:   {stats['median']:.2f}")
    kind = "population" if args.population else "sample"
    print(f"  Std dev:  {stats['std dev']:.2f} ({kind})")
    print(f"  Highest:  {stats['highest']:.2f} ({', '.join(hi)})")
    print(f"  Lowest:   {stats['lowest']:.2f} ({', '.join(lo)})")
    print(f"  Mean GPA: {statistics.mean(gpas):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
