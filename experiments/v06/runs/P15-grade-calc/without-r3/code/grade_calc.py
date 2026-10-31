#!/usr/bin/env python3
"""Grade calculator: weighted final grades, letter grades, GPA points and class stats.

Scores CSV: first column is the student name, remaining columns are assessments
(scores on a 0-100 scale, blank = missing).

Weights: inline "Exam=50,HW=30" or a file path. A file may be JSON
({"Exam": 50, "HW": 30}) or lines of "name,weight" / "name=weight" / "name: weight"
(a "name,weight" header line is skipped). Weights are normalized to sum to 100.
"""
import argparse
import csv
import json
import math
import os
import statistics
import sys

# (minimum percent, letter, GPA points), checked top-down.
GRADE_SCALE = [
    (97, "A+", 4.0), (93, "A", 4.0), (90, "A-", 3.7),
    (87, "B+", 3.3), (83, "B", 3.0), (80, "B-", 2.7),
    (77, "C+", 2.3), (73, "C", 2.0), (70, "C-", 1.7),
    (67, "D+", 1.3), (63, "D", 1.0), (60, "D-", 0.7),
]


class GradeError(Exception):
    pass


def parse_weight_pairs(text):
    weights = {}
    items = text.replace("\n", ",").split(",") if "=" in text or ":" in text else None
    if items is not None:
        for item in items:
            item = item.strip()
            if not item:
                continue
            sep = "=" if "=" in item else ":"
            name, _, value = item.partition(sep)
            weights[name.strip()] = value.strip()
    else:  # "name,weight" per line
        for row in csv.reader(text.splitlines()):
            if len(row) >= 2 and row[0].strip():
                weights[row[0].strip()] = row[1].strip()
    return weights


def load_weights(spec):
    if os.path.isfile(spec):
        with open(spec, newline="", encoding="utf-8-sig") as f:
            text = f.read()
        if text.lstrip().startswith("{"):
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as e:
                raise GradeError(f"invalid weights JSON: {e}")
        else:
            raw = parse_weight_pairs(text)
    else:
        raw = parse_weight_pairs(spec)

    weights = {}
    for name, value in raw.items():
        if isinstance(value, str):
            value = value.strip().rstrip("%")
        try:
            w = float(value)
        except (TypeError, ValueError):
            if not weights and str(value).lower() in ("weight", "pct", "percent"):
                continue  # header row
            raise GradeError(f"weight for '{name}' is not a number: {value!r}")
        if not math.isfinite(w) or w < 0:
            raise GradeError(f"weight for '{name}' must be a non-negative number")
        weights[name] = w
    if not weights:
        raise GradeError("no weights defined")
    return weights


def normalize_weights(weights):
    """Scale weights to sum to 100. Returns (normalized, original_total)."""
    total = sum(weights.values())
    if total <= 0:
        raise GradeError("weights must sum to more than zero")
    return {k: v * 100.0 / total for k, v in weights.items()}, total


def load_scores(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            raise GradeError("scores CSV is empty")
        if len(header) < 2:
            raise GradeError("scores CSV needs a student column and at least one assessment")
        students = []
        for lineno, row in enumerate(reader, start=2):
            if not any(c.strip() for c in row):
                continue
            name = row[0].strip()
            if not name:
                raise GradeError(f"line {lineno}: missing student name")
            scores = {}
            for col, cell in zip(header[1:], row[1:]):
                cell = cell.strip()
                if not cell:
                    continue
                try:
                    val = float(cell.rstrip("%"))
                except ValueError:
                    raise GradeError(f"line {lineno}: invalid score {cell!r} for {name} in '{col}'")
                if not math.isfinite(val) or val < 0:
                    raise GradeError(f"line {lineno}: score for {name} in '{col}' must be >= 0")
                scores[col] = val
            students.append((name, scores))
    if not students:
        raise GradeError("scores CSV has no students")
    return header[1:], students


def final_grade(scores, weights, missing):
    """Weighted grade in percent, or None if nothing to grade."""
    if missing == "skip":
        present = {k: w for k, w in weights.items() if k in scores}
        total = sum(present.values())
        if total <= 0:
            return None
        return sum(scores[k] * w for k, w in present.items()) / total
    return sum(scores.get(k, 0.0) * w for k, w in weights.items()) / 100.0


def letter_and_gpa(pct):
    rounded = round(pct + 1e-9, 2)
    for minimum, letter, gpa in GRADE_SCALE:
        if rounded >= minimum:
            return letter, gpa
    return "F", 0.0


def class_stats(values):
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "highest": max(values),
        "lowest": min(values),
    }


def render_table(rows, headers):
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    def fmt(r):
        return "  ".join(
            str(c).ljust(widths[i]) if i == 0 else str(c).rjust(widths[i]) for i, c in enumerate(r)
        )
    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines += [fmt(r) for r in rows]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Compute weighted grades from a CSV of scores.")
    p.add_argument("scores", help="CSV file: student name column followed by assessment columns")
    p.add_argument("-w", "--weights", required=True,
                   help='weights file (JSON or name,weight lines) or inline "Exam=50,HW=30"')
    p.add_argument("--missing", choices=("zero", "skip"), default="zero",
                   help="treat blank scores as zero (default) or re-weight over completed work")
    p.add_argument("--sort", choices=("input", "grade", "name"), default="input")
    args = p.parse_args(argv)

    try:
        weights = load_weights(args.weights)
        columns, students = load_scores(args.scores)

        absent = [k for k in weights if k not in columns]
        if absent:
            raise GradeError("weighted assessments not in scores CSV: " + ", ".join(absent))
        ignored = [c for c in columns if c not in weights]
        weights, total = normalize_weights(weights)
    except (GradeError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if abs(total - 100.0) > 1e-9:
        print(f"note: weights summed to {total:g}, normalized to 100%", file=sys.stderr)
    if ignored:
        print("note: ignoring columns with no weight: " + ", ".join(ignored), file=sys.stderr)

    results = []
    ungraded = []
    for name, scores in students:
        pct = final_grade(scores, weights, args.missing)
        if pct is None:
            ungraded.append(name)
            continue
        letter, gpa = letter_and_gpa(pct)
        results.append((name, pct, letter, gpa))
    for name in ungraded:
        print(f"warning: {name} has no scores for weighted assessments; excluded", file=sys.stderr)
    if not results:
        print("error: no gradable students", file=sys.stderr)
        return 1

    if args.sort == "grade":
        results.sort(key=lambda r: -r[1])
    elif args.sort == "name":
        results.sort(key=lambda r: r[0].lower())

    print("Weights (normalized):")
    for k, w in weights.items():
        print(f"  {k}: {w:.2f}%")
    print()
    print(render_table([(n, f"{pct:.2f}", l, f"{g:.1f}") for n, pct, l, g in results],
                       ["Student", "Final %", "Grade", "GPA"]))

    st = class_stats([r[1] for r in results])
    gpa_mean = statistics.fmean(r[3] for r in results)
    best = max(results, key=lambda r: r[1])
    worst = min(results, key=lambda r: r[1])
    print(f"\nClass statistics (n={len(results)}):")
    print(f"  Mean:     {st['mean']:.2f}")
    print(f"  Median:   {st['median']:.2f}")
    print(f"  Std dev:  {st['stdev']:.2f} (sample)")
    print(f"  Highest:  {st['highest']:.2f} ({best[0]})")
    print(f"  Lowest:   {st['lowest']:.2f} ({worst[0]})")
    print(f"  Mean GPA: {gpa_mean:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
