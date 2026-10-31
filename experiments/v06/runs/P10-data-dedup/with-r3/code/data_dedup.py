#!/usr/bin/env python3
"""Remove duplicate rows from a CSV by a (composite) key."""
import argparse
import csv
import sys


def dedup(rows, key_idx, strategy):
    """Return (kept_rows, dups); dups maps key tuple -> occurrences (keys seen > once)."""
    groups = {}
    for pos, row in enumerate(rows):
        key = tuple(row[i] if i < len(row) else "" for i in key_idx)
        groups.setdefault(key, []).append(pos)
    dups = {k: len(v) for k, v in groups.items() if len(v) > 1}
    if strategy == "last":
        keep = sorted(v[-1] for v in groups.values())
    else:
        keep = sorted(v[0] for v in groups.values())
    return [rows[p] for p in keep], dups


def main(argv=None):
    p = argparse.ArgumentParser(description="Deduplicate a CSV by key columns.")
    p.add_argument("input", help="input CSV (with header)")
    p.add_argument("-k", "--key", required=True,
                   help="comma-separated key column names (composite key)")
    p.add_argument("-s", "--strategy", choices=["first", "last", "error"],
                   default="first", help="keep first, keep last, or error (default: first)")
    p.add_argument("-o", "--output", required=True, help="output CSV path")
    args = p.parse_args(argv)

    def fail(msg):
        print(f"error: {msg}", file=sys.stderr)
        return 2

    try:
        with open(args.input, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return fail("input CSV is empty (no header)")
            rows = [r for r in reader if r]
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        return fail(f"cannot read {args.input}: {e}")

    names = [n.strip() for n in args.key.split(",") if n.strip()]
    if not names:
        return fail("no key columns given")
    missing = [n for n in names if n not in header]
    if missing:
        return fail("key column(s) not in header: " + ", ".join(missing))
    key_idx = [header.index(n) for n in names]

    kept, dups = dedup(rows, key_idx, args.strategy)
    found = sum(c - 1 for c in dups.values())

    if args.strategy == "error" and dups:
        print(f"error: {found} duplicate row(s) in {len(dups)} key(s):", file=sys.stderr)
        for k, c in dups.items():
            print(f"  key {dict(zip(names, k))} appears {c} times", file=sys.stderr)
        return 1
    try:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(kept)
    except OSError as e:
        return fail(f"cannot write {args.output}: {e}")

    print(f"Duplicates found: {found}; removed: {len(rows) - len(kept)}; "
          f"rows written: {len(kept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
