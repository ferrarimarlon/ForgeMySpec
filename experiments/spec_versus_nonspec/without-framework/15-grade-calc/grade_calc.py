#!/usr/bin/env python3
"""Grade Calculator — WITHOUT framework. Direct implementation."""
import argparse
import csv
import sys

def read_grades(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try: score = float(row.get("score") or 0)
            except: score = 0
            try: max_score = float(row.get("max_score") or 100)
            except: max_score = 100
            try: weight = float(row.get("weight") or 1)
            except: weight = 1
            rows.append({"student": row["student"], "assignment": row["assignment"],
                         "score": score, "max_score": max_score, "weight": weight})
    return rows

def compute(assignments):
    total_w = sum(a["weight"] for a in assignments)
    if not total_w: return 0
    return round(sum((a["weight"]/total_w) * (a["score"]/a["max_score"])*100 for a in assignments), 2)

def grade(avg):
    if avg >= 90: return "A"
    if avg >= 80: return "B"
    if avg >= 70: return "C"
    if avg >= 60: return "D"
    return "F"

GPA = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}

def median(vals):
    s = sorted(vals); n = len(s)
    if not n: return 0
    return s[n//2] if n % 2 else (s[n//2-1]+s[n//2])/2

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
r = sub.add_parser("report"); r.add_argument("grades_csv")
s = sub.add_parser("student"); s.add_argument("name"); s.add_argument("grades_csv")

args = parser.parse_args()

if args.cmd == "report":
    rows = read_grades(args.grades_csv)
    students = {}
    for row in rows:
        students.setdefault(row["student"], []).append(row)
    results = {}
    for name, asgns in students.items():
        avg = compute(asgns)
        g = grade(avg)
        results[name] = {"avg": avg, "grade": g, "gpa": GPA[g], "pass": avg >= 60}

    print(f"{'Student':<25} {'Avg':>6} {'Grade':>6} {'GPA':>5} {'Pass':>5}")
    print("-" * 55)
    for name, d in sorted(results.items()):
        print(f"{name:<25} {d['avg']:>6.2f} {d['grade']:>6} {d['gpa']:>5.1f} {'Yes' if d['pass'] else 'No':>5}")

    gpas = [d["gpa"] for d in results.values()]
    print(f"\nClass stats: mean={sum(gpas)/len(gpas):.2f} median={median(gpas):.2f} high={max(gpas):.1f} low={min(gpas):.1f}")

elif args.cmd == "student":
    rows = read_grades(args.grades_csv)
    asgns = [r for r in rows if r["student"] == args.name]
    if not asgns: print(f"Not found: {args.name}", file=sys.stderr); sys.exit(1)
    avg = compute(asgns)
    g = grade(avg)
    print(f"{args.name}: avg={avg:.2f}% grade={g} gpa={GPA[g]:.1f} pass={'Yes' if avg>=60 else 'No'}")
