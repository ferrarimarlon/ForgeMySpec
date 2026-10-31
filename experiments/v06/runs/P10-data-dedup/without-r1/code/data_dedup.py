#!/usr/bin/env python3
"""Remove duplicate rows from a CSV file by a (composite) key.

Strategies:
  first  keep the first row seen for each key (default)
  last   keep the last row seen for each key
  error  write nothing, report the duplicates, exit with status 1

Exit status: 0 success, 1 duplicates found with --strategy error, 2 usage/input error.
"""
import argparse
import csv
import os
import sys


class DedupError(Exception):
    pass


def parse_keys(values):
    keys = []
    for v in values:
        keys.extend(k.strip() for k in v.split(",") if k.strip())
    if not keys:
        raise DedupError("at least one key column is required")
    return keys


def read_rows(path, delimiter, encoding):
    with open(path, newline="", encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            raise DedupError(f"{path}: file is empty (no header row)")
        rows = [(reader.line_num, row) for row in reader if row]
    return header, rows


def resolve_key_indexes(header, keys):
    missing = [k for k in keys if k not in header]
    if missing:
        raise DedupError(
            f"key column(s) not found: {', '.join(missing)} "
            f"(available: {', '.join(header)})"
        )
    dupes = [k for k in keys if header.count(k) > 1]
    if dupes:
        raise DedupError(f"key column(s) ambiguous (repeated in header): {', '.join(dupes)}")
    return [header.index(k) for k in keys]


def make_key(row, idxs):
    # Short rows are treated as having empty trailing fields.
    return tuple(row[i] if i < len(row) else "" for i in idxs)


def dedupe(rows, idxs, strategy):
    """Return (kept_rows, groups) where groups maps key -> [line numbers] for keys seen >1 time."""
    seen = {}  # key -> list of (line, row)
    for line, row in rows:
        seen.setdefault(make_key(row, idxs), []).append((line, row))
    groups = {k: [ln for ln, _ in v] for k, v in seen.items() if len(v) > 1}
    pick = 0 if strategy == "first" else -1
    kept = sorted((v[pick] for v in seen.values()), key=lambda t: t[0])
    return [row for _, row in kept], groups


def main(argv=None):
    p = argparse.ArgumentParser(description="Remove duplicate CSV rows by a composite key.")
    p.add_argument("input", help="input CSV file")
    p.add_argument("-o", "--output", help="output CSV file (required unless --strategy error)")
    p.add_argument("-k", "--key", action="append", required=True, metavar="COL",
                   help="key column name; repeat or comma-separate for a composite key")
    p.add_argument("-s", "--strategy", choices=["first", "last", "error"], default="first",
                   help="which duplicate to keep, or fail (default: first)")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default: ,)")
    p.add_argument("-e", "--encoding", default="utf-8-sig", help="file encoding (default: utf-8-sig)")
    args = p.parse_args(argv)

    try:
        if len(args.delimiter) != 1:
            raise DedupError("delimiter must be a single character")
        if args.strategy != "error" and not args.output:
            raise DedupError("--output is required for strategies 'first' and 'last'")
        if args.output and os.path.exists(args.output) and os.path.samefile(args.input, args.output):
            raise DedupError("output must differ from input")

        keys = parse_keys(args.key)
        header, rows = read_rows(args.input, args.delimiter, args.encoding)
        idxs = resolve_key_indexes(header, keys)
        kept, groups = dedupe(rows, idxs, args.strategy)
        n_dupes = len(rows) - len(kept)

        if args.strategy == "error" and groups:
            print(f"error: found {n_dupes} duplicate row(s) across {len(groups)} key(s) "
                  f"[key: {', '.join(keys)}]", file=sys.stderr)
            for key, lines in groups.items():
                print(f"  {dict(zip(keys, key))} on lines {', '.join(map(str, lines))}",
                      file=sys.stderr)
            return 1

        if args.output:
            with open(args.output, "w", newline="", encoding=args.encoding.replace("-sig", "")) as f:
                w = csv.writer(f, delimiter=args.delimiter)
                w.writerow(header)
                w.writerows(kept)
    except (DedupError, OSError, UnicodeError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"Rows read:        {len(rows)}")
    print(f"Duplicate keys:   {len(groups)}")
    print(f"Duplicates found: {n_dupes}")
    print(f"Duplicates removed: {n_dupes if args.strategy != 'error' else 0}")
    print(f"Rows written:     {len(kept) if args.output else 0}")
    if args.output:
        print(f"Output:           {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
