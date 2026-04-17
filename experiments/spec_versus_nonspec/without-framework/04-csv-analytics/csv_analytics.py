import csv
import json
import sys
import argparse
import statistics
import re
from pathlib import Path

def load_rows(input_path):
    p = Path(input_path)
    files = list(p.glob("*.csv")) if p.is_dir() else [p]
    rows = []
    for f in files:
        with open(f) as fp:
            reader = csv.DictReader(fp)
            rows.extend(list(reader))
    return rows

def is_numeric(col, rows):
    vals = [r[col] for r in rows if r.get(col, "").strip()]
    if not vals:
        return False
    try:
        [float(v) for v in vals]
        return True
    except ValueError:
        return False

def get_vals(col, rows):
    result = []
    for r in rows:
        v = r.get(col, "").strip()
        if v:
            try:
                result.append(float(v))
            except ValueError:
                pass
    return result

def compute(col, rows):
    numeric = is_numeric(col, rows)
    non_empty = [r[col] for r in rows if r.get(col, "").strip()]
    if not numeric:
        return {"count": len(non_empty), "min": None, "max": None, "mean": None, "median": None, "stdev": None}
    vals = get_vals(col, rows)
    if not vals:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None, "stdev": None}
    try:
        std = round(statistics.stdev(vals), 4)
    except statistics.StatisticsError:
        std = 0.0
    return {
        "count": len(vals),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "mean": round(statistics.mean(vals), 4),
        "median": round(statistics.median(vals), 4),
        "stdev": std,
    }

def filter_rows(rows, expr):
    m = re.match(r"(\S+)\s*(==|!=|>=|<=|>|<)\s*(.+)", expr.strip())
    if not m:
        print("Bad filter", file=sys.stderr); sys.exit(1)
    col, op, val = m.groups()
    val = val.strip()
    def check(r):
        cv = r.get(col, "")
        try:
            a, b = float(cv), float(val)
        except ValueError:
            a, b = cv, val
        return eval(f"a {op} b")
    return [r for r in rows if check(r)]

def print_table(stats):
    print(f"{'Column':<20}  {'Count':<6}  {'Min':<10}  {'Max':<10}  {'Mean':<10}  {'Median':<10}  {'Stdev':<10}")
    print("-" * 84)
    for col, s in stats.items():
        def v(x): return "-" if x is None else str(x)
        print(f"{col[:20]:<20}  {s['count']:<6}  {v(s['min']):<10}  {v(s['max']):<10}  {v(s['mean']):<10}  {v(s['median']):<10}  {v(s['stdev']):<10}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--filter", dest="filter_expr", default=None)
    p.add_argument("--columns", default=None)
    p.add_argument("--output", default="report.json")
    args = p.parse_args()

    rows = load_rows(args.input)
    if args.filter_expr:
        rows = filter_rows(rows, args.filter_expr)

    cols = list(rows[0].keys()) if rows else []
    if args.columns:
        cols = [c.strip() for c in args.columns.split(",")]

    stats = {col: compute(col, rows) for col in cols}
    print_table(stats)
    with open(args.output, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Report: {args.output}")

if __name__ == "__main__":
    main()
