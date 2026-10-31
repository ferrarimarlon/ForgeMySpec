#!/usr/bin/env python3
"""CSV Analytics Tool: per-column stats, row filtering, column selection, JSON report.

Examples:
  csv_analytics.py data.csv
  csv_analytics.py data.csv -w "age>30" -w "city==Paris" -c age,salary -o report.json
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
    "==": operator.eq, "!=": operator.ne,
    ">=": operator.ge, "<=": operator.le,
    ">": operator.gt, "<": operator.lt,
}
# Longest operators first so ">=" is not parsed as ">".
COND_RE = re.compile(r"^\s*(.+?)\s*(==|!=|>=|<=|>|<|~=)\s*(.*?)\s*$")


def to_number(value):
    """Return float for a numeric string, else None."""
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def read_csv(path, delimiter=","):
    """Return (header, rows) where rows are dicts. Use '-' for stdin."""
    f = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")
    try:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"{path}: no header row found")
        header = [h.strip() for h in reader.fieldnames]
        reader.fieldnames = header
        rows = []
        for r in reader:
            # Short rows give None, extra cells land under key None; normalize.
            r.pop(None, None)
            rows.append({k: ("" if v is None else v) for k, v in r.items()})
        return header, rows
    finally:
        if f is not sys.stdin:
            f.close()


def parse_condition(text, header):
    m = COND_RE.match(text)
    if not m:
        raise ValueError(f"invalid filter {text!r}; use COLUMN OP VALUE "
                         "with OP in == != > >= < <= ~=")
    col, op, val = m.groups()
    if col not in header:
        raise ValueError(f"filter column {col!r} not found; columns: {', '.join(header)}")
    return col, op, val


def matches(row, cond):
    col, op, val = cond
    cell = row.get(col, "")
    if op == "~=":  # case-insensitive substring
        return val.lower() in cell.lower()
    a, b = to_number(cell), to_number(val)
    if a is not None and b is not None:
        return OPS[op](a, b)
    if op in ("==", "!="):
        return OPS[op](cell.strip(), val)
    # Ordering comparison on non-numeric: compare as strings, skip empty cells.
    if not cell.strip():
        return False
    return OPS[op](cell.strip(), val)


def filter_rows(rows, header, conditions):
    conds = [parse_condition(c, header) for c in conditions]
    return [r for r in rows if all(matches(r, c) for c in conds)]


def select_columns(header, spec):
    if not spec:
        return header
    cols = [c.strip() for c in spec.split(",") if c.strip()]
    missing = [c for c in cols if c not in header]
    if missing:
        raise ValueError(f"unknown column(s): {', '.join(missing)}; "
                         f"columns: {', '.join(header)}")
    return cols


def column_stats(rows, col):
    """Stats for one column. Numeric stats are present if any cell is numeric."""
    values = [r.get(col, "") for r in rows]
    nonempty = [v for v in values if v.strip()]
    nums = [n for n in map(to_number, values) if n is not None]
    out = {
        "count": len(nonempty),
        "missing": len(values) - len(nonempty),
        "numeric_count": len(nums),
        "unique": len(set(v.strip() for v in nonempty)),
    }
    if nums:
        out["type"] = "numeric" if len(nums) == len(nonempty) else "mixed"
        out.update({
            "min": min(nums),
            "max": max(nums),
            "mean": statistics.fmean(nums),
            "median": statistics.median(nums),
            "stdev": statistics.stdev(nums) if len(nums) > 1 else None,
        })
    else:
        out["type"] = "text" if nonempty else "empty"
        if nonempty:
            stripped = [v.strip() for v in nonempty]
            out["min"], out["max"] = min(stripped), max(stripped)
    return out


def build_report(path, header, rows, columns, total_rows, filters, include_rows):
    report = {
        "file": path,
        "total_rows": total_rows,
        "matched_rows": len(rows),
        "filters": filters,
        "columns": {c: column_stats(rows, c) for c in columns},
    }
    if include_rows:
        report["rows"] = [{c: r.get(c, "") for c in columns} for r in rows]
    return report


def fmt(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)


def print_table(report, out):
    out.write(f"{report['file']}: {report['matched_rows']}/{report['total_rows']} rows\n")
    keys = ["type", "count", "missing", "min", "max", "mean", "median", "stdev"]
    rows = [["column"] + keys]
    for c, s in report["columns"].items():
        rows.append([c] + [fmt(s.get(k)) for k in keys])
    widths = [max(len(r[i]) for r in rows) for i in range(len(keys) + 1)]
    for r in rows:
        out.write("  ".join(v.ljust(w) for v, w in zip(r, widths)).rstrip() + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description="CSV analytics: stats, filter, select, JSON export.")
    p.add_argument("files", nargs="+", help="CSV file(s); '-' reads stdin")
    p.add_argument("-c", "--columns", help="comma-separated columns to include")
    p.add_argument("-w", "--where", action="append", default=[], metavar="COND",
                   help="filter, e.g. 'age>30' (ops: == != > >= < <= ~=); repeatable, ANDed")
    p.add_argument("-o", "--output", help="write JSON report to this file (default: table on stdout)")
    p.add_argument("--json", action="store_true", help="print JSON to stdout instead of table")
    p.add_argument("--rows", action="store_true", help="include filtered rows in JSON report")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    args = p.parse_args(argv)

    reports = []
    try:
        for path in args.files:
            header, rows = read_csv(path, args.delimiter)
            matched = filter_rows(rows, header, args.where)
            cols = select_columns(header, args.columns)
            reports.append(build_report(path, header, matched, cols, len(rows),
                                        args.where, args.rows))
    except (OSError, ValueError, csv.Error, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    payload = reports[0] if len(reports) == 1 else {"reports": reports}
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {args.output}", file=sys.stderr)
    elif args.json:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for r in reports:
            print_table(r, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
