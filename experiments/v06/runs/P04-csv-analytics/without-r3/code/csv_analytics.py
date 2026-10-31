#!/usr/bin/env python3
"""CSV Analytics Tool: per-column stats, row filtering, column selection, JSON report.

Examples:
  csv_analytics.py data.csv
  csv_analytics.py data.csv -w "age>30" -w "city=Paris" -c age,salary -o report.json
  csv_analytics.py a.csv b.csv --rows 5

Filter operators: == = != >= <= > < ~ (substring, case-insensitive)
Numeric comparison is used when both sides parse as numbers, else string comparison.
"""
import argparse
import csv
import json
import math
import re
import statistics
import sys

OPS = ["==", "!=", ">=", "<=", "=", ">", "<", "~"]
_FILTER_RE = re.compile(r"^\s*(.+?)\s*(==|!=|>=|<=|=|>|<|~)\s*(.*?)\s*$")


def to_number(s):
    """Return float for a numeric string, else None (NaN/inf are rejected)."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        v = float(s.replace(",", "")) if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", s) else float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def read_csv(path, delimiter=","):
    """Return (fieldnames, rows as list of dicts)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"{path}: no header row")
        names = [n.strip() for n in reader.fieldnames]
        if len(set(names)) != len(names):
            raise ValueError(f"{path}: duplicate column names in header")
        reader.fieldnames = names
        rows = []
        for r in reader:
            r.pop(None, None)  # drop extra cells beyond header
            rows.append({k: (v if v is not None else "") for k, v in r.items()})
    return names, rows


def parse_filter(expr, columns):
    m = _FILTER_RE.match(expr)
    if not m:
        raise ValueError(f"invalid filter: {expr!r}")
    col, op, val = m.groups()
    if col not in columns:
        raise ValueError(f"filter column {col!r} not found; available: {', '.join(columns)}")
    return col, ("==" if op == "=" else op), val


def match(row, flt):
    col, op, val = flt
    cell = row.get(col, "").strip()
    if op == "~":
        return val.lower() in cell.lower()
    a, b = to_number(cell), to_number(val)
    if a is not None and b is not None:
        x, y = a, b
    else:
        if op in ("<", ">", "<=", ">=") and (a is None or b is None) and cell == "":
            return False
        x, y = cell, val
    return {
        "==": x == y, "!=": x != y, ">": x > y, "<": x < y, ">=": x >= y, "<=": x <= y,
    }[op]


def filter_rows(rows, filters):
    return [r for r in rows if all(match(r, f) for f in filters)]


def column_stats(rows, col):
    values = [r[col] for r in rows]
    nonblank = [v for v in values if v.strip() != ""]
    nums = [n for n in (to_number(v) for v in nonblank) if n is not None]
    out = {
        "total": len(values),
        "missing": len(values) - len(nonblank),
        "count": len(nums),
    }
    if nonblank and len(nums) == len(nonblank):
        out["type"] = "numeric"
    elif nums:
        out["type"] = "mixed"
    else:
        out["type"] = "text"
    if nums:
        out.update(
            min=min(nums),
            max=max(nums),
            mean=statistics.fmean(nums),
            median=statistics.median(nums),
            stdev=statistics.stdev(nums) if len(nums) > 1 else None,
        )
    else:
        out.update(min=None, max=None, mean=None, median=None, stdev=None)
        out["count"] = len(nonblank)
        out["unique"] = len(set(nonblank))
    return out


def build_report(path, columns, rows, total_rows, filters, delimiter):
    return {
        "file": path,
        "total_rows": total_rows,
        "matched_rows": len(rows),
        "filters": [f"{c}{o}{v}" for c, o, v in filters],
        "columns": {c: column_stats(rows, c) for c in columns},
    }


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) >= 1e6 or (v != 0 and abs(v) < 1e-3) else f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v)


def print_table(report):
    print(f"{report['file']}: {report['matched_rows']}/{report['total_rows']} rows")
    heads = ["column", "type", "count", "missing", "min", "max", "mean", "median", "stdev"]
    table = [heads] + [
        [c] + [fmt(s[h]) for h in heads[1:]] for c, s in report["columns"].items()
    ]
    widths = [max(len(r[i]) for r in table) for i in range(len(heads))]
    for i, r in enumerate(table):
        print("  ".join(x.ljust(w) if j < 2 else x.rjust(w) for j, (x, w) in enumerate(zip(r, widths))))
        if i == 0:
            print("  ".join("-" * w for w in widths))


def main(argv=None):
    p = argparse.ArgumentParser(description="CSV analytics: stats, filter, select, JSON export.",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("Examples:")[1].join(["Examples:", ""]))
    p.add_argument("files", nargs="+", help="input CSV file(s)")
    p.add_argument("-c", "--columns", help="comma-separated columns to include")
    p.add_argument("-w", "--where", action="append", default=[], metavar="EXPR",
                   help="filter, e.g. 'age>30' (repeatable; ANDed)")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", help="write JSON report to this file ('-' for stdout)")
    p.add_argument("--rows", type=int, default=0, metavar="N",
                   help="include first N matching rows in the JSON report")
    p.add_argument("-q", "--quiet", action="store_true", help="suppress the text table")
    a = p.parse_args(argv)

    if a.delimiter == "\\t":
        a.delimiter = "\t"
    if len(a.delimiter) != 1:
        p.error("delimiter must be a single character")

    reports = []
    try:
        for path in a.files:
            names, rows = read_csv(path, a.delimiter)
            filters = [parse_filter(w, names) for w in a.where]
            cols = names
            if a.columns:
                cols = [c.strip() for c in a.columns.split(",") if c.strip()]
                bad = [c for c in cols if c not in names]
                if bad:
                    raise ValueError(f"{path}: unknown column(s): {', '.join(bad)}")
            matched = filter_rows(rows, filters)
            rep = build_report(path, cols, matched, len(rows), filters, a.delimiter)
            if a.rows > 0:
                rep["sample_rows"] = [{c: r[c] for c in cols} for r in matched[: a.rows]]
            reports.append(rep)
    except (OSError, ValueError, csv.Error, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not a.quiet and a.output != "-":
        for rep in reports:
            print_table(rep)
            print()
    if a.output:
        data = reports[0] if len(reports) == 1 else {"reports": reports}
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if a.output == "-":
            print(text)
        else:
            try:
                with open(a.output, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
            except OSError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            if not a.quiet:
                print(f"JSON report written to {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
