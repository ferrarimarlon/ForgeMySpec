#!/usr/bin/env python3
"""Grade Calculator CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: weight normalization, >= boundaries, GPA-based class stats.
"""
import argparse
import csv
import sys
from typing import Dict, List, Optional, Tuple


def read_grades(path: str) -> List[dict]:
    """Read grades CSV. Handle missing scores as 0."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle missing score
            score_str = row.get("score", "").strip()
            try:
                score = float(score_str) if score_str else 0.0
            except ValueError:
                score = 0.0
            max_score_str = row.get("max_score", "").strip()
            try:
                max_score = float(max_score_str) if max_score_str else 100.0
            except ValueError:
                max_score = 100.0
            weight_str = row.get("weight", "").strip()
            try:
                weight = float(weight_str) if weight_str else 1.0
            except ValueError:
                weight = 1.0
            rows.append({
                "student": row.get("student", "").strip(),
                "assignment": row.get("assignment", "").strip(),
                "score": score,
                "max_score": max_score,
                "weight": weight,
            })
    return rows


def compute_student_avg(assignments: List[dict]) -> float:
    """Compute weight-normalized weighted average (0-100 scale)."""
    total_weight = sum(a["weight"] for a in assignments)
    if total_weight == 0:
        return 0.0
    weighted_sum = 0.0
    for a in assignments:
        norm_weight = a["weight"] / total_weight
        pct = (a["score"] / a["max_score"] * 100) if a["max_score"] > 0 else 0.0
        weighted_sum += norm_weight * pct
    return round(weighted_sum, 2)


def letter_grade(avg: float) -> str:
    """Letter grade with >= boundaries as specified."""
    if avg >= 90:
        return "A"
    elif avg >= 80:
        return "B"
    elif avg >= 70:
        return "C"
    elif avg >= 60:
        return "D"
    else:
        return "F"


def gpa_from_letter(letter: str) -> float:
    mapping = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
    return mapping.get(letter, 0.0)


def median(values: List[float]) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    else:
        return round((sorted_vals[mid - 1] + sorted_vals[mid]) / 2, 4)


def compute_all_students(rows: List[dict]) -> Dict[str, dict]:
    """Group by student and compute stats."""
    by_student: Dict[str, List[dict]] = {}
    for row in rows:
        name = row["student"]
        if name not in by_student:
            by_student[name] = []
        by_student[name].append(row)

    results = {}
    for student, assignments in by_student.items():
        avg = compute_student_avg(assignments)
        letter = letter_grade(avg)
        gpa = gpa_from_letter(letter)
        results[student] = {
            "avg": avg,
            "letter": letter,
            "gpa": gpa,
            "pass": avg >= 60,
            "assignments": len(assignments),
        }
    return results


def class_stats(student_data: Dict[str, dict]) -> dict:
    """Compute class statistics from GPA values."""
    gpas = [s["gpa"] for s in student_data.values()]
    if not gpas:
        return {}
    return {
        "mean_gpa": round(sum(gpas) / len(gpas), 4),
        "median_gpa": median(gpas),
        "highest_gpa": max(gpas),
        "lowest_gpa": min(gpas),
        "student_count": len(gpas),
        "pass_count": sum(1 for s in student_data.values() if s["pass"]),
    }


def print_report(student_data: Dict[str, dict], stats: dict) -> None:
    print(f"{'Student':<25} {'Avg':>6} {'Grade':>6} {'GPA':>5} {'Pass':>5}")
    print("-" * 55)
    for student, data in sorted(student_data.items()):
        pass_str = "Yes" if data["pass"] else "No"
        print(
            f"{student:<25} {data['avg']:>6.2f} {data['letter']:>6} "
            f"{data['gpa']:>5.1f} {pass_str:>5}"
        )
    print("-" * 55)
    print(f"\nClass Statistics (GPA-based):")
    print(f"  Students:   {stats.get('student_count', 0)}")
    print(f"  Passing:    {stats.get('pass_count', 0)}")
    print(f"  Mean GPA:   {stats.get('mean_gpa', 0):.2f}")
    print(f"  Median GPA: {stats.get('median_gpa', 0):.2f}")
    print(f"  Highest:    {stats.get('highest_gpa', 0):.1f}")
    print(f"  Lowest:     {stats.get('lowest_gpa', 0):.1f}")


def cmd_report(args: argparse.Namespace) -> None:
    rows = read_grades(args.grades_csv)
    student_data = compute_all_students(rows)
    stats = class_stats(student_data)
    print_report(student_data, stats)


def cmd_student(args: argparse.Namespace) -> None:
    rows = read_grades(args.grades_csv)
    student_rows = [r for r in rows if r["student"] == args.name]
    if not student_rows:
        print(f"Student '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    avg = compute_student_avg(student_rows)
    letter = letter_grade(avg)
    gpa = gpa_from_letter(letter)
    print(f"Student: {args.name}")
    print(f"  Assignments: {len(student_rows)}")
    print(f"  Weighted Avg: {avg:.2f}%")
    print(f"  Letter Grade: {letter}")
    print(f"  GPA: {gpa:.1f}")
    print(f"  Pass: {'Yes' if avg >= 60 else 'No'}")
    print(f"\n  Assignment Detail:")
    total_weight = sum(r["weight"] for r in student_rows)
    for r in student_rows:
        norm_w = r["weight"] / total_weight if total_weight > 0 else 0
        pct = (r["score"] / r["max_score"] * 100) if r["max_score"] > 0 else 0
        print(f"    {r['assignment']:<20} {r['score']}/{r['max_score']} ({pct:.1f}%) weight={r['weight']} norm={norm_w:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade Calculator CLI")
    sub = parser.add_subparsers(dest="command")

    p_rep = sub.add_parser("report", help="Full class grade report")
    p_rep.add_argument("grades_csv", help="Grades CSV file")

    p_stu = sub.add_parser("student", help="Show individual student report")
    p_stu.add_argument("name", help="Student name")
    p_stu.add_argument("grades_csv", help="Grades CSV file")

    args = parser.parse_args()
    if args.command == "report":
        cmd_report(args)
    elif args.command == "student":
        cmd_student(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
