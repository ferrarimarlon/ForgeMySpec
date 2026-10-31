#!/usr/bin/env python3
"""CSV Analytics Tool: per-column stats, row filtering, column selection, JSON report.

Examples:
  csv_analytics.py data.csv
  csv_analytics.py data.csv -w "age>30" -w "city=Paris" -c age,salary -o report.json
  csv_analytics.py a.csv b.csv --rows
"""
import argparse
import csv
import json
import math
import operator
import re
import statistics
import sys

OPS = {
    ">=": operator.ge, "<=": operator.le, "!=": operator.ne,
    "==": operator.eq, "=": operator.eq, ">": operator.gt, "<": operator.lt,
    "~": lambda a, b: re.search(b, a) is not None,
}
# Longest operators first so ">=" is not parsed as ">".
_COND_RE = re.compile(r"^\s*(.+?)\s*(>=|<=|!=|==|=|>|<|~)\s*(.*?)\s*$")


def to_number(s):
    """Return float for numeric strings, else None (blank/NaN/inf are non-numeric)."""
    if s is None:
        return None
    try:
        v = float(s.strip())
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def read_csv(path, delimiter=","):
    f = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")
    with f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"{path}: no header row")
        rows = []
        for r in reader:
            r.pop(None, None)  # drop extra cells beyond the header
            rows.append(r)
        return list(reader.fieldnames), rows


def parse_condition(expr, columns):
    m = _COND_RE.match(expr)
    if not m:
        raise ValueError(f"bad filter {expr!r}; use COLUMN OP VALUE")
    col, op, val = m.groups()
    if col not in columns:
        raise ValueError(f"filter column {col!r} not found; have {columns}")
    if op == "~":
        re.compile(val)  # validate early
    return col, op, val


def matches(row, cond):
    col, op, val = cond
    cell = row.get(col)
    if cell is None:
        return False
    if op == "~":
        return OPS[op](cell, val)
    a, b = to_number(cell), to_number(val)
    if a is not None and b is not None:
        return OPS[op](a, b)
    if op in ("=", "==", "!="):
        return OPS[op](cell.strip(), val)
    return False  # ordering comparisons need numbers


def column_stats(values):
    """Stats over raw string values. Numeric stats use only numeric cells."""
    blanks = sum(1 for v in values if v is None or not v.strip())
    nums = [n for n in map(to_number, values) if n is not None]
    out = {"count": len(values) - blanks, "missing": blanks, "numeric_count": len(nums)}
    if nums:
        out.update(
            min=min(nums), max=max(nums),
            mean=statistics.fmean(nums), median=statistics.median(nums),
            stdev=statistics.stdev(nums) if len(nums) > 1 else None,
        )
    else:
        out.update(min=None, max=None, mean=None, median=None, stdev=None)
    return out


def analyze(columns, rows):
    return {c: column_stats([r.get(c) for r in rows]) for c in columns}


def fmt(v):
    return "-" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v)


def print_table(stats, out):
    heads = ["column", "count", "missing", "min", "max", "mean", "median", "stdev"]
    table = [heads] + [[c] + [fmt(s[h]) for h in heads[1:]] for c, s in stats.items()]
    widths = [max(len(r[i]) for r in table) for i in range(len(heads))]
    for i, r in enumerate(table):
        print("  ".join(x.ljust(w) if j == 0 else x.rjust(w)
                        for j, (x, w) in enumerate(zip(r, widths))), file=out)
        if i == 0:
            print("  ".join("-" * w for w in widths), file=out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+", help="CSV file(s); '-' for stdin")
    p.add_argument("-c", "--columns", help="comma-separated columns to keep")
    p.add_argument("-w", "--where", action="append", default=[], metavar="COND",
                   help="filter, e.g. 'age>30', 'city=Paris', 'name~^A' (regex); "
                        "repeatable, ANDed")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ,)")
    p.add_argument("-o", "--output", help="write JSON report to this file")
    p.add_argument("--rows", action="store_true", help="include filtered rows in JSON")
    p.add_argument("--json", action="store_true", help="print JSON to stdout, not a table")
    a = p.parse_args(argv)

    try:
        report = {}
        for path in a.files:
            columns, rows = read_csv(path, a.delimiter)
            total = len(rows)
            conds = [parse_condition(w, columns) for w in a.where]
            rows = [r for r in rows if all(matches(r, c) for c in conds)]
            if a.columns:
                want = [c.strip() for c in a.columns.split(",") if c.strip()]
                missing = [c for c in want if c not in columns]
                if missing:
                    raise ValueError(f"{path}: unknown column(s) {missing}; have {columns}")
                columns = want
            entry = {"rows_total": total, "rows_matched": len(rows),
                     "filters": a.where, "columns": columns,
                     "stats": analyze(columns, rows)}
            if a.rows:
                entry["rows"] = [{c: r.get(c) for c in columns} for r in rows]
            report[path] = entry
    except (OSError, ValueError, re.error, csv.Error, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
    if a.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        for path, e in report.items():
            print(f"== {path}: {e['rows_matched']}/{e['rows_total']} rows ==")
            print_table(e["stats"], sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
