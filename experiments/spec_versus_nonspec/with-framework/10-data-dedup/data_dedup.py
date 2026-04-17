#!/usr/bin/env python3
"""Data Deduplicator CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: composite keys, first/last/error strategies, --report flag.
"""
import argparse
import csv
import sys
from typing import List, Tuple


def read_csv(path: str) -> Tuple[List[str], List[dict]]:
    """Read CSV file. Returns (headers, rows)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return list(headers), rows


def write_csv(path: str, headers: List[str], rows: List[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def get_key(row: dict, keys: List[str]) -> tuple:
    return tuple(row.get(k, "") for k in keys)


def deduplicate(
    headers: List[str],
    rows: List[dict],
    keys: List[str],
    strategy: str,
    report: bool,
) -> Tuple[List[dict], int]:
    """Deduplicate rows. Returns (deduped_rows, duplicate_count)."""
    seen = {}  # key -> list of row indices
    for i, row in enumerate(rows):
        k = get_key(row, keys)
        if k not in seen:
            seen[k] = []
        seen[k].append(i)

    duplicates = {k: idxs for k, idxs in seen.items() if len(idxs) > 1}
    total_dupes = sum(len(idxs) - 1 for idxs in duplicates.values())

    if report:
        if duplicates:
            print(f"Duplicate summary ({len(duplicates)} key(s) with duplicates):")
            for k, idxs in sorted(duplicates.items(), key=lambda x: str(x[0])):
                key_str = ", ".join(str(v) for v in k)
                print(f"  Key ({key_str}): {len(idxs) - 1} duplicate(s)")
        else:
            print("No duplicates found.")

    if strategy == "error":
        if duplicates:
            print(f"ERROR: Found {len(duplicates)} duplicate key(s):", file=sys.stderr)
            for k in sorted(duplicates.keys(), key=str):
                key_str = ", ".join(str(v) for v in k)
                print(f"  - ({key_str})", file=sys.stderr)
            sys.exit(1)
        return rows, 0

    if strategy == "first":
        deduped = []
        seen_keys = set()
        for row in rows:
            k = get_key(row, keys)
            if k not in seen_keys:
                deduped.append(row)
                seen_keys.add(k)
    elif strategy == "last":
        last = {}
        order = []
        for row in rows:
            k = get_key(row, keys)
            if k not in last:
                order.append(k)
            last[k] = row
        deduped = [last[k] for k in order]
    else:
        print(f"Error: unknown strategy '{strategy}'", file=sys.stderr)
        sys.exit(1)

    return deduped, total_dupes


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV Data Deduplicator")
    parser.add_argument("input", help="Input CSV file")
    parser.add_argument("--keys", required=True, help="Comma-separated key columns")
    parser.add_argument("--strategy", choices=["first", "last", "error"], default="first",
                        help="Deduplication strategy")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--report", action="store_true", help="Print duplicate summary")

    args = parser.parse_args()
    key_cols = [k.strip() for k in args.keys.split(",")]

    headers, rows = read_csv(args.input)

    # Validate key columns exist
    missing = [k for k in key_cols if k not in headers]
    if missing:
        print(f"Error: key column(s) not found in CSV: {missing}", file=sys.stderr)
        sys.exit(1)

    deduped, dupe_count = deduplicate(headers, rows, key_cols, args.strategy, args.report)

    write_csv(args.output, headers, deduped)
    removed = len(rows) - len(deduped)
    print(f"Done: {len(rows)} rows in → {len(deduped)} rows out ({removed} duplicates removed)")


if __name__ == "__main__":
    main()
