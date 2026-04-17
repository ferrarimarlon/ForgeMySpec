import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

FILTER_RE = re.compile(r"^\s*(\S+)\s*(==|!=|>=|<=|>|<)\s*(.+)\s*$")

# ── Data loading ──────────────────────────────────────────────────────────────

def load_csv(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # strip whitespace from field names
            reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]
            for row in reader:
                rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


def resolve_inputs(input_path: str) -> list[Path]:
    p = Path(input_path)
    if p.is_dir():
        files = sorted(p.glob("*.csv"))
        if not files:
            print(f"Error: no .csv files found in {p}", file=sys.stderr)
            sys.exit(1)
        return files
    if not p.exists():
        print(f"Error: file not found: {p}", file=sys.stderr)
        sys.exit(1)
    return [p]


# ── Filtering ─────────────────────────────────────────────────────────────────

def _compare(cell_val: str, op: str, filter_val: str) -> bool:
    try:
        a, b = float(cell_val), float(filter_val)
        ops = {"==": a == b, "!=": a != b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}
    except ValueError:
        a, b = cell_val, filter_val
        ops = {"==": a == b, "!=": a != b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}
    return ops[op]


def apply_filter(rows: list[dict], filter_str: str) -> list[dict]:
    m = FILTER_RE.match(filter_str)
    if not m:
        print(f"Error: cannot parse filter expression: {filter_str!r}", file=sys.stderr)
        sys.exit(1)
    col, op, val = m.group(1), m.group(2), m.group(3).strip()
    if rows and col not in rows[0]:
        print(f"Warning: filter column {col!r} not found — no rows filtered.", file=sys.stderr)
        return rows
    return [r for r in rows if _compare(r.get(col, ""), op, val)]


# ── Stats ─────────────────────────────────────────────────────────────────────

def is_numeric_col(col: str, rows: list[dict]) -> bool:
    values = [r[col] for r in rows if r.get(col) != ""]
    if not values:
        return False
    try:
        [float(v) for v in values]
        return True
    except ValueError:
        return False


def collect_numeric(col: str, rows: list[dict]) -> list[float]:
    result = []
    for r in rows:
        v = r.get(col, "")
        if v == "":
            continue
        try:
            result.append(float(v))
        except ValueError:
            pass
    return result


def compute_stats(col: str, rows: list[dict], numeric: bool) -> dict:
    non_missing = [r[col] for r in rows if r.get(col, "") != ""]
    count = len(non_missing)
    if not numeric:
        return {"count": count, "min": None, "max": None,
                "mean": None, "median": None, "stdev": None}
    vals = collect_numeric(col, rows)
    if not vals:
        return {"count": 0, "min": None, "max": None,
                "mean": None, "median": None, "stdev": None}
    mean = round(statistics.mean(vals), 4)
    median = round(statistics.median(vals), 4)
    try:
        stdev = round(statistics.stdev(vals), 4)
    except statistics.StatisticsError:
        stdev = 0.0
    return {
        "count": len(vals),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "mean": mean,
        "median": median,
        "stdev": stdev,
    }


# ── Output ────────────────────────────────────────────────────────────────────

def _cell(v, width: int) -> str:
    s = "-" if v is None else str(v)
    return s[:width].ljust(width)


def print_table(stats_map: dict) -> None:
    W = {"col": 20, "count": 6, "num": 10}
    header = (
        _cell("Column", W["col"]) + "  " +
        _cell("Count", W["count"]) + "  " +
        _cell("Min", W["num"]) + "  " +
        _cell("Max", W["num"]) + "  " +
        _cell("Mean", W["num"]) + "  " +
        _cell("Median", W["num"]) + "  " +
        _cell("Stdev", W["num"])
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for col, s in stats_map.items():
        print(
            _cell(col, W["col"]) + "  " +
            _cell(s["count"], W["count"]) + "  " +
            _cell(s["min"], W["num"]) + "  " +
            _cell(s["max"], W["num"]) + "  " +
            _cell(s["mean"], W["num"]) + "  " +
            _cell(s["median"], W["num"]) + "  " +
            _cell(s["stdev"], W["num"])
        )
    print(sep)


def write_report(stats_map: dict, output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats_map, f, indent=2)
    print(f"Report written to {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="csv_analytics",
        description="Descriptive statistics for CSV files.",
    )
    p.add_argument("input", help="CSV file or directory of CSV files")
    p.add_argument("--filter", dest="filter_expr", default=None,
                   metavar="EXPR", help="Row filter, e.g. 'age > 30'")
    p.add_argument("--columns", default=None,
                   metavar="COL1,COL2", help="Comma-separated column names to analyse")
    p.add_argument("--output", default="report.json",
                   metavar="PATH", help="JSON output path (default: report.json)")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    paths = resolve_inputs(args.input)
    rows = load_csv(paths)

    if args.filter_expr:
        rows = apply_filter(rows, args.filter_expr)

    if not rows:
        print("No rows to analyse after filtering.", file=sys.stderr)
        sys.exit(0)

    all_cols = list(rows[0].keys())
    if args.columns:
        selected = [c.strip() for c in args.columns.split(",")]
        unknown = [c for c in selected if c not in all_cols]
        for u in unknown:
            print(f"Warning: column {u!r} not found — skipped.", file=sys.stderr)
        cols = [c for c in selected if c in all_cols]
    else:
        cols = all_cols

    stats_map = {}
    for col in cols:
        numeric = is_numeric_col(col, rows)
        stats_map[col] = compute_stats(col, rows, numeric)

    print_table(stats_map)
    write_report(stats_map, Path(args.output))


if __name__ == "__main__":
    main()
