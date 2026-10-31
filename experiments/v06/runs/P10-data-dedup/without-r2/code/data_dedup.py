#!/usr/bin/env python3
"""Remove duplicate rows from a CSV by a key made of one or more columns."""

import argparse
import csv
import sys


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Deduplicate a CSV file by key column(s).")
    p.add_argument("input", help="input CSV path ('-' for stdin)")
    p.add_argument("output", help="output CSV path ('-' for stdout)")
    p.add_argument("-k", "--key", required=True,
                   help="comma-separated column names forming the key")
    p.add_argument("-s", "--strategy", choices=["first", "last", "error"],
                   default="first", help="which duplicate to keep (default: first)")
    p.add_argument("-d", "--delimiter", default=",", help="CSV delimiter (default: ',')")
    p.add_argument("-e", "--encoding", default="utf-8-sig", help="file encoding (default: utf-8-sig)")
    return p.parse_args(argv)


def dedup(rows, key_idx, strategy):
    """Return (kept_rows, duplicate_groups, dup_count).

    duplicate_groups maps key -> list of 1-based data row numbers sharing it.
    """
    kept = {}  # key -> row (dict preserves first-seen key order)
    seen_rows = {}  # key -> list of row numbers
    dup_count = 0
    for n, row in enumerate(rows, start=1):
        key = tuple(row[i] for i in key_idx)
        seen_rows.setdefault(key, []).append(n)
        if key in kept:
            dup_count += 1
            if strategy == "last":
                kept[key] = row
        else:
            kept[key] = row
    groups = {k: v for k, v in seen_rows.items() if len(v) > 1}
    return list(kept.values()), groups, dup_count


def main(argv=None):
    args = parse_args(argv)
    keys = [k.strip() for k in args.key.split(",") if k.strip()]
    if not keys:
        print("error: no key columns given", file=sys.stderr)
        return 2

    try:
        fin = sys.stdin if args.input == "-" else open(
            args.input, newline="", encoding=args.encoding)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    with fin:
        reader = csv.reader(fin, delimiter=args.delimiter)
        header = next(reader, None)
        if header is None:
            print("error: input is empty", file=sys.stderr)
            return 2
        missing = [k for k in keys if k not in header]
        if missing:
            print(f"error: key column(s) not in header: {', '.join(missing)}",
                  file=sys.stderr)
            return 2
        key_idx = [header.index(k) for k in keys]
        rows = []
        for lineno, row in enumerate(reader, start=2):
            if not row:  # skip blank lines
                continue
            if len(row) <= max(key_idx):
                print(f"error: line {lineno} is missing key column(s)", file=sys.stderr)
                return 2
            rows.append(row)

    kept, groups, dup_count = dedup(rows, key_idx, args.strategy)
    total = len(rows)

    if args.strategy == "error":
        if groups:
            print(f"error: found {dup_count} duplicate row(s) in {len(groups)} key(s):",
                  file=sys.stderr)
            for key, nums in groups.items():
                label = ", ".join(f"{k}={v!r}" for k, v in zip(keys, key))
                print(f"  {label}: data rows {', '.join(map(str, nums))}", file=sys.stderr)
            print("no output written", file=sys.stderr)
            return 1

    try:
        fout = sys.stdout if args.output == "-" else open(
            args.output, "w", newline="", encoding=args.encoding.replace("-sig", ""))
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    with fout:
        w = csv.writer(fout, delimiter=args.delimiter)
        w.writerow(header)
        w.writerows(kept)

    summary = sys.stderr if args.output == "-" else sys.stdout
    print(f"rows read:        {total}", file=summary)
    print(f"duplicates found: {dup_count} (in {len(groups)} key(s))", file=summary)
    print(f"duplicates removed: {dup_count}", file=summary)
    print(f"rows written:     {len(kept)}", file=summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
