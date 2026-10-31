#!/usr/bin/env python3
"""CSV analytics: per-column stats, row filters, column selection, JSON report."""
import argparse
import csv
import json
import operator
import re
import statistics
import sys

OPS = {
    "==": operator.eq, "!=": operator.ne,
    "<=": operator.le, ">=": operator.ge,
    "<": operator.lt, ">": operator.gt,
}
FILTER_RE = re.compile(r"^\s*(.+?)\s*(==|!=|<=|>=|<|>)\s*(.*?)\s*$")


class UsageError(Exception):
    """Invalid user input; reported with exit code 2."""


def _num(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def read_csv(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            if not header:
                raise UsageError(f"{path}: empty CSV (no header)")
            rows = list(reader)
    except OSError as e:
        raise UsageError(f"cannot read {path}: {e.strerror or e}")
    except (csv.Error, UnicodeDecodeError) as e:
        raise UsageError(f"cannot parse {path}: {e}")
    return list(header), rows


def parse_filter(expr, header):
    m = FILTER_RE.match(expr)
    if not m:
        raise UsageError(f"bad filter {expr!r}: expected COLUMN OP VALUE")
    col, op, val = m.groups()
    if col not in header:
        raise UsageError(f"unknown column in filter: {col}")
    return col, op, val


def _match(cell, op, val):
    if cell is None:
        return False
    a, b = _num(cell), _num(val)
    if a is not None and b is not None:
        return OPS[op](a, b)
    return OPS[op](cell, val)


def filter_rows(rows, filters):
    return [r for r in rows
            if all(_match(r.get(c), op, v) for c, op, v in filters)]


def _clean(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def column_stats(rows, columns):
    out = {}
    for col in columns:
        cells = [r.get(col) for r in rows]
        cells = [c for c in cells if c is not None and c.strip() != ""]
        nums = [_num(c) for c in cells]
        stat = {"count": len(cells), "min": None, "max": None,
                "mean": None, "median": None, "stdev": None}
        if cells and all(n is not None for n in nums):
            stat["min"] = _clean(min(nums))
            stat["max"] = _clean(max(nums))
            stat["mean"] = statistics.fmean(nums)
            stat["median"] = statistics.median(nums)
            if len(nums) >= 2:
                stat["stdev"] = statistics.stdev(nums)
        out[col] = stat
    return out


def build_report(path, filters=(), columns=None):
    header, rows = read_csv(path)
    parsed = [parse_filter(f, header) for f in filters]
    if columns is not None:
        for c in columns:
            if c not in header:
                raise UsageError(f"unknown column: {c}")
        header = columns
    rows = filter_rows(rows, parsed)
    return {"file": path, "rows": len(rows),
            "columns": column_stats(rows, header)}


def main(argv=None):
    p = argparse.ArgumentParser(description="CSV analytics JSON report")
    p.add_argument("file")
    p.add_argument("--filter", action="append", default=[], metavar="EXPR",
                   help="COLUMN OP VALUE (OP: == != < <= > >=); repeatable, ANDed")
    p.add_argument("--columns", help="comma-separated columns to keep")
    p.add_argument("--output", help="write the JSON report here (default stdout)")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    cols = None
    if args.columns is not None:
        cols = [c.strip() for c in args.columns.split(",") if c.strip()]
        if not cols:
            print("error: --columns is empty", file=sys.stderr)
            return 2
    try:
        report = build_report(args.file, args.filter, cols)
        text = json.dumps(report, indent=2)
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
            except OSError as e:
                raise UsageError(f"cannot write {args.output}: {e.strerror or e}")
        else:
            print(text)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
