#!/usr/bin/env python3
"""Remove duplicate rows from a CSV file by a (composite) key.

Strategies: first (keep first occurrence), last (keep last occurrence),
error (exit non-zero and report duplicates; no output written).
"""
import argparse
import csv
import sys


class DedupError(Exception):
    pass


def dedupe(header, rows, key_cols, strategy):
    """Return (kept_rows, duplicates).

    duplicates maps key tuple -> list of 1-based data row numbers (all
    occurrences) for every key that appears more than once.
    """
    missing = [c for c in key_cols if c not in header]
    if missing:
        raise DedupError("key column(s) not found in header: " + ", ".join(missing))
    idx = [header.index(c) for c in key_cols]
    positions = {}
    for n, row in enumerate(rows, 1):
        if len(row) != len(header):
            raise DedupError("row %d has %d fields, expected %d" % (n, len(row), len(header)))
        key = tuple(row[i] for i in idx)
        positions.setdefault(key, []).append(n)
    duplicates = {k: v for k, v in positions.items() if len(v) > 1}
    if strategy == "error":
        return list(rows), duplicates
    pick = 0 if strategy == "first" else -1
    keep = {v[pick] for v in positions.values()}
    return [r for n, r in enumerate(rows, 1) if n in keep], duplicates


def run(args, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        with open(args.input, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                raise DedupError("input file is empty (no header)")
            rows = list(reader)
    except OSError as e:
        print("error: cannot read input: %s" % e, file=err)
        return 2
    try:
        kept, dups = dedupe(header, rows, args.key, args.strategy)
    except DedupError as e:
        print("error: %s" % e, file=err)
        return 2
    found = sum(len(v) - 1 for v in dups.values())
    if args.strategy == "error":
        if dups:
            print("error: %d duplicate row(s) found in %d key(s):" % (found, len(dups)), file=err)
            for key, nums in dups.items():
                desc = ", ".join("%s=%s" % (c, v) for c, v in zip(args.key, key))
                print("  key (%s): rows %s" % (desc, ", ".join(map(str, nums))), file=err)
            print("Duplicates found: %d, removed: 0" % found, file=out)
            return 1
        removed = 0
    else:
        removed = len(rows) - len(kept)
    try:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(kept)
    except OSError as e:
        print("error: cannot write output: %s" % e, file=err)
        return 2
    print("Duplicates found: %d, removed: %d" % (found, removed), file=out)
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Remove duplicate CSV rows by a composite key.")
    p.add_argument("input", help="input CSV file (with header row)")
    p.add_argument("output", help="output CSV file")
    p.add_argument("-k", "--key", nargs="+", required=True, metavar="COLUMN",
                   help="one or more key column names")
    p.add_argument("-s", "--strategy", choices=["first", "last", "error"], default="first",
                   help="which duplicate to keep, or fail (default: first)")
    return p


def main(argv=None):
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
