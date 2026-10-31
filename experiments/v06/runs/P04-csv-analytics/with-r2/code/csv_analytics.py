#!/usr/bin/env python3
"""CSV Analytics Tool: read CSV, filter rows, select columns, per-column stats, JSON report."""
import argparse
import csv
import json
import math
import operator
import re
import statistics
import sys

OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_FILTER_RE = re.compile(r"^\s*(.+?)\s*(==|!=|<=|>=|<|>)\s*(.*?)\s*$")


class CsvAnalyticsError(Exception):
    pass


def read_csv(path):
    """Return (header, rows) where rows are dicts keyed by header names."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                raise CsvAnalyticsError("empty CSV file: %s" % path)
            rows = []
            for rec in reader:
                if not rec:
                    continue
                rec = rec + [""] * (len(header) - len(rec))
                rows.append(dict(zip(header, rec)))
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
        raise CsvAnalyticsError("cannot read %s: %s" % (path, e.strerror or e))
    return header, rows


def _to_float(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def column_stats(header, rows):
    """Per-column stats: count, min, max, mean, median, stdev (sample)."""
    result = {}
    for col in header:
        cells = [r.get(col, "") for r in rows]
        cells = [c for c in cells if c.strip() != ""]
        nums = [_to_float(c) for c in cells]
        if cells and all(n is not None for n in nums):
            result[col] = {
                "count": len(nums),
                "min": min(nums),
                "max": max(nums),
                "mean": statistics.fmean(nums),
                "median": statistics.median(nums),
                "stdev": statistics.stdev(nums) if len(nums) >= 2 else None,
            }
        else:
            result[col] = {
                "count": len(cells),
                "min": min(cells) if cells else None,
                "max": max(cells) if cells else None,
                "mean": None,
                "median": None,
                "stdev": None,
            }
    return result


def parse_filter(expr):
    m = _FILTER_RE.match(expr)
    if not m:
        raise CsvAnalyticsError("bad filter expression: %r" % expr)
    return m.group(1), m.group(2), m.group(3)


def filter_rows(rows, exprs, header=None):
    """Keep rows satisfying all 'COLUMN OP VALUE' expressions."""
    parsed = [parse_filter(e) for e in exprs]
    if header is None:
        header = list(rows[0].keys()) if rows else None
    for col, _, _ in parsed:
        if header is not None and col not in header:
            raise CsvAnalyticsError("unknown column in filter: %s" % col)

    def ok(row):
        for col, op, val in parsed:
            cell = row.get(col, "")
            a, b = _to_float(cell), _to_float(val)
            if a is not None and b is not None:
                if not OPS[op](a, b):
                    return False
            elif b is not None and cell.strip() == "":
                if op != "!=":  # an empty cell never satisfies a numeric comparison
                    return False
            elif not OPS[op](cell, val):
                return False
        return True

    return [r for r in rows if ok(r)]


def select_columns(header, rows, cols):
    """Keep only cols, in the requested order."""
    for c in cols:
        if c not in header:
            raise CsvAnalyticsError("unknown column: %s" % c)
    return list(cols), [{c: r.get(c, "") for c in cols} for r in rows]


def build_report(path, select=None, filters=()):
    header, rows = read_csv(path)
    total = len(rows)
    rows = filter_rows(rows, filters, header)
    if select:
        header, rows = select_columns(header, rows, select)
    return {
        "source": path,
        "total_rows": total,
        "row_count": len(rows),
        "columns": list(header),
        "stats": column_stats(header, rows),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="CSV analytics: stats, filter, select, JSON report")
    p.add_argument("file")
    p.add_argument("--select", help="comma-separated columns to keep")
    p.add_argument("--filter", action="append", default=[], help="COLUMN OP VALUE (repeatable, ANDed)")
    p.add_argument("--output", help="write JSON report to this file (default: stdout)")
    args = p.parse_args(argv)
    select = [c.strip() for c in args.select.split(",")] if args.select else None
    try:
        report = build_report(args.file, select, args.filter)
    except CsvAnalyticsError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
