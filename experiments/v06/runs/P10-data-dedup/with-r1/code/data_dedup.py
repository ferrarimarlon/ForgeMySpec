#!/usr/bin/env python3
"""Remove duplicate CSV rows by a (composite) key. Stdlib only."""
import argparse
import csv
import sys


def dedup(rows, key_idx, strategy):
    """Return (kept_rows, duplicates); duplicates maps key -> occurrence count (>1 only)."""
    groups = {}
    for i, row in enumerate(rows):
        key = tuple(row[j] if j < len(row) else "" for j in key_idx)
        groups.setdefault(key, []).append(i)
    dups = {k: len(v) for k, v in groups.items() if len(v) > 1}
    if strategy == "last":
        keep = sorted(v[-1] for v in groups.values())
    else:
        keep = sorted(v[0] for v in groups.values())
    return [rows[i] for i in keep], dups


def main(argv=None):
    p = argparse.ArgumentParser(description="Remove duplicate CSV rows by key columns.")
    p.add_argument("input", help="input CSV (with header)")
    p.add_argument("-k", "--key", nargs="+", required=True, help="key column name(s)")
    p.add_argument("-o", "--output", required=True, help="output CSV path")
    p.add_argument("-s", "--strategy", choices=["first", "last", "error"], default="first")
    args = p.parse_args(argv)

    try:
        with open(args.input, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                print("error: input CSV is empty", file=sys.stderr)
                return 2
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        print(f"error: cannot read {args.input}: {e}", file=sys.stderr)
        return 2

    missing = [c for c in args.key if c not in header]
    if missing:
        print(f"error: unknown key column(s): {', '.join(missing)}", file=sys.stderr)
        return 2
    key_idx = [header.index(c) for c in args.key]

    kept, dups = dedup(rows, key_idx, args.strategy)
    found = len(rows) - len(kept)

    if args.strategy == "error" and dups:
        print(f"error: {found} duplicate row(s) found in {len(dups)} key(s); nothing written",
              file=sys.stderr)
        for k, n in dups.items():
            print(f"  duplicate key {dict(zip(args.key, k))} appears {n} times", file=sys.stderr)
        print(f"Summary: duplicates found: {found}, removed: 0")
        return 1

    try:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(kept)
    except OSError as e:
        print(f"error: cannot write {args.output}: {e}", file=sys.stderr)
        return 2
    print(f"Summary: duplicates found: {found}, removed: {found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
