#!/usr/bin/env python3
"""CSV Analytics Tool: per-column stats, row filters, column selection, JSON report.

Standard library only.

Usage:
    python3 csv_analytics.py data.csv [-c col ...] [-f "col > 3" ...] [-o report.json]
"""
import argparse
import csv
import json
import math
import statistics
import sys


class UsageError(Exception):
    """Invalid user input; the CLI exits with code 2."""


OPS = ("<=", ">=", "==", "!=", "<", ">")


def read_csv(path):
    """Read a CSV file with a header row. Returns (columns, rows of dicts)."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            columns = list(reader.fieldnames or [])
            rows = [{c: (r.get(c) or "") for c in columns} for r in reader]
    except OSError as exc:
        raise UsageError(f"cannot read file '{path}': {exc.strerror or exc}")
    except csv.Error as exc:
        raise UsageError(f"malformed CSV '{path}': {exc}")
    if not columns:
        raise UsageError(f"file '{path}' has no header row")
    return columns, rows


def _num(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_filter(expr, columns):
    """Parse 'COLUMN OP VALUE' into (column, op, value)."""
    for op in OPS:
        if op in expr:
            col, _, val = expr.partition(op)
            col, val = col.strip(), val.strip()
            if not col:
                break
            if col not in columns:
                raise UsageError(f"unknown column in filter '{expr}': {col}")
            return col, op, val
    raise UsageError(f"malformed filter '{expr}': expected COLUMN OP VALUE "
                     f"with OP in {', '.join(OPS)}")


def _matches(cell, op, value):
    a, b = _num(cell), _num(value)
    if a is None or b is None:
        a, b = cell, value
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    return a >= b


def filter_rows(rows, filters, columns):
    """Keep rows matching every filter (AND)."""
    parsed = [parse_filter(f, columns) for f in filters]
    return [r for r in rows
            if all(_matches(r[c], op, v) for c, op, v in parsed)]


def select_columns(columns, rows, selected):
    """Keep only the named columns, in the given order."""
    for c in selected:
        if c not in columns:
            raise UsageError(f"unknown column: {c}")
    return list(selected), [{c: r[c] for c in selected} for r in rows]


def column_stats(rows, column):
    """count/min/max/mean/median/stdev for one column (empty cells skipped)."""
    cells = [r[column] for r in rows if r[column].strip() != ""]
    nums = [_num(c) for c in cells]
    if cells and all(n is not None for n in nums):
        return {
            "type": "numeric",
            "count": len(nums),
            "min": min(nums),
            "max": max(nums),
            "mean": statistics.fmean(nums),
            "median": statistics.median(nums),
            "stdev": statistics.stdev(nums) if len(nums) > 1 else None,
        }
    return {
        "type": "text",
        "count": len(cells),
        "min": min(cells) if cells else None,
        "max": max(cells) if cells else None,
        "mean": None,
        "median": None,
        "stdev": None,
    }


def build_report(path, filters=(), selected=None):
    columns, rows = read_csv(path)
    rows = filter_rows(rows, filters, columns)
    if selected:
        columns, rows = select_columns(columns, rows, selected)
    return {
        "source": path,
        "row_count": len(rows),
        "columns": {c: column_stats(rows, c) for c in columns},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="CSV analytics: stats report as JSON")
    p.add_argument("csv_file")
    p.add_argument("-c", "--columns", nargs="+", metavar="COL",
                   help="select these columns, in this order")
    p.add_argument("-f", "--filter", action="append", default=[], metavar="EXPR",
                   help="row filter 'COLUMN OP VALUE' (repeatable, ANDed)")
    p.add_argument("-o", "--output", help="write the JSON report here (default: stdout)")
    args = p.parse_args(argv)
    try:
        report = build_report(args.csv_file, args.filter, args.columns)
        text = json.dumps(report, indent=2)
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
            except OSError as exc:
                raise UsageError(f"cannot write '{args.output}': {exc.strerror or exc}")
        else:
            print(text)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
