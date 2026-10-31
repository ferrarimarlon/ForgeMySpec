#!/usr/bin/env python3
"""Remove duplicate rows from a CSV by a (composite) key.

Strategies:
  first  keep the first row seen for each key
  last   keep the last row seen for each key (output keeps order of the kept rows)
  error  write nothing, report duplicates and exit non-zero
"""
import argparse
import csv
import sys


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Deduplicate a CSV file by key column(s).")
    p.add_argument("input", help="input CSV path ('-' for stdin)")
    p.add_argument("output", help="output CSV path ('-' for stdout)")
    p.add_argument("-k", "--key", required=True,
                   help="comma-separated key column names, or 0-based indexes with --no-header")
    p.add_argument("-s", "--strategy", choices=["first", "last", "error"], default="first",
                   help="which duplicate to keep (default: first)")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default: ,)")
    p.add_argument("--no-header", action="store_true", help="input has no header row")
    p.add_argument("--ignore-case", action="store_true", help="compare keys case-insensitively")
    p.add_argument("--strip", action="store_true", help="strip whitespace around key values")
    p.add_argument("--encoding", default="utf-8-sig", help="input encoding (default: utf-8-sig)")
    return p.parse_args(argv)


def resolve_key_indexes(key_spec, header, ncols_hint, no_header):
    parts = [k.strip() for k in key_spec.split(",") if k.strip()]
    if not parts:
        raise ValueError("no key columns given")
    if no_header:
        try:
            idx = [int(k) for k in parts]
        except ValueError:
            raise ValueError("with --no-header, keys must be 0-based integer indexes")
        if any(i < 0 for i in idx):
            raise ValueError("column indexes must be >= 0")
        return idx
    missing = [k for k in parts if k not in header]
    if missing:
        raise ValueError("key column(s) not in header: %s (available: %s)"
                         % (", ".join(missing), ", ".join(header)))
    return [header.index(k) for k in parts]


def make_key(row, idx, ignore_case, strip):
    vals = []
    for i in idx:
        if i >= len(row):
            raise IndexError(i)
        v = row[i]
        if strip:
            v = v.strip()
        if ignore_case:
            v = v.casefold()
        vals.append(v)
    return tuple(vals)


def main(argv=None):
    args = parse_args(argv)
    if len(args.delimiter) != 1:
        print("error: delimiter must be a single character", file=sys.stderr)
        return 2

    fin = sys.stdin if args.input == "-" else open(args.input, newline="", encoding=args.encoding)
    try:
        reader = csv.reader(fin, delimiter=args.delimiter)
        header = None
        if not args.no_header:
            header = next(reader, None)
            if header is None:
                print("error: input is empty", file=sys.stderr)
                return 2
        try:
            idx = resolve_key_indexes(args.key, header, None, args.no_header)
        except ValueError as e:
            print("error: %s" % e, file=sys.stderr)
            return 2

        total = 0
        # key -> list of line numbers (for reporting); kept: key -> (order, row)
        kept = {}
        lines = {}
        line_no = 1 if header else 0
        for row in reader:
            line_no += 1
            if not row:  # skip blank lines
                continue
            try:
                key = make_key(row, idx, args.ignore_case, args.strip)
            except IndexError as e:
                print("error: line %d has too few columns for key index %s" % (line_no, e),
                      file=sys.stderr)
                return 2
            total += 1
            lines.setdefault(key, []).append(line_no)
            if key not in kept:
                kept[key] = row
            elif args.strategy == "last":
                # re-insert so output order follows position of the kept row
                del kept[key]
                kept[key] = row
    finally:
        if fin is not sys.stdin:
            fin.close()

    dup_keys = {k: v for k, v in lines.items() if len(v) > 1}
    removed = total - len(kept)

    if args.strategy == "error" and dup_keys:
        print("error: found %d duplicate row(s) across %d key(s); no output written"
              % (removed, len(dup_keys)), file=sys.stderr)
        for k, ls in dup_keys.items():
            print("  key %s: lines %s" % (", ".join(repr(x) for x in k),
                                         ", ".join(map(str, ls))), file=sys.stderr)
        return 1

    fout = sys.stdout if args.output == "-" else open(args.output, "w", newline="", encoding="utf-8")
    try:
        writer = csv.writer(fout, delimiter=args.delimiter)
        if header is not None:
            writer.writerow(header)
        writer.writerows(kept.values())
    finally:
        if fout is not sys.stdout:
            fout.close()

    # Summary goes to stderr when the CSV itself is on stdout.
    out = sys.stderr if args.output == "-" else sys.stdout
    print("rows read: %d" % total, file=out)
    print("duplicate keys: %d" % len(dup_keys), file=out)
    print("duplicates found: %d" % removed, file=out)
    print("duplicates removed: %d" % removed, file=out)
    print("rows written: %d" % len(kept), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
