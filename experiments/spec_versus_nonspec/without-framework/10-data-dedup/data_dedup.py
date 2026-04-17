#!/usr/bin/env python3
"""Data Deduplicator — WITHOUT framework. Direct implementation."""
import argparse
import csv
import sys

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("--keys", required=True)
parser.add_argument("--strategy", choices=["first","last","error"], default="first")
parser.add_argument("--output", required=True)
parser.add_argument("--report", action="store_true")
args = parser.parse_args()

keys = [k.strip() for k in args.keys.split(",")]

with open(args.input, newline="") as f:
    reader = csv.DictReader(f)
    headers = list(reader.fieldnames or [])
    rows = list(reader)

# Validate keys
missing = [k for k in keys if k not in headers]
if missing:
    print(f"Error: columns not found: {missing}", file=sys.stderr); sys.exit(1)

def get_key(row):
    return tuple(row.get(k, "") for k in keys)

# Group by key
groups = {}
order = []
for row in rows:
    k = get_key(row)
    if k not in groups:
        groups[k] = []; order.append(k)
    groups[k].append(row)

dupes = {k: v for k,v in groups.items() if len(v) > 1}

if args.report:
    for k, v in dupes.items():
        print(f"Key {k}: {len(v)-1} duplicate(s)")

if args.strategy == "error":
    if dupes:
        for k in dupes: print(f"Duplicate: {k}", file=sys.stderr)
        sys.exit(1)
    result = rows
elif args.strategy == "first":
    result = [groups[k][0] for k in order]
elif args.strategy == "last":
    result = [groups[k][-1] for k in order]

with open(args.output, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(result)

removed = len(rows) - len(result)
print(f"{len(rows)} -> {len(result)} rows ({removed} removed)")
