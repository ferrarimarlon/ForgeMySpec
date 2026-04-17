#!/usr/bin/env python3
"""Config Validator — WITHOUT framework. Direct implementation."""
import argparse
import json
import re
import sys

TYPE_MAP = {"string": str, "int": int, "float": float, "bool": bool, "list": list, "dict": dict}

def get_val(config, key):
    parts = key.split(".")
    cur = config
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None, False
        cur = cur[p]
    return cur, True

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
v = sub.add_parser("validate"); v.add_argument("config"); v.add_argument("schema")
args = parser.parse_args()

if args.cmd != "validate":
    parser.print_help(); sys.exit(0)

config = json.load(open(args.config))
schema = json.load(open(args.schema))

errors = []
for key, rules in schema.items():
    val, found = get_val(config, key)
    if not found:
        if rules.get("required"):
            errors.append(f"[{key}] required but missing")
        continue

    if "type" in rules:
        expected = TYPE_MAP.get(rules["type"])
        if expected and not isinstance(val, expected):
            # bool is subclass of int — reject
            if rules["type"] == "int" and isinstance(val, bool):
                errors.append(f"[{key}] expected int, got bool")
            else:
                errors.append(f"[{key}] expected {rules['type']}, got {type(val).__name__}")

    if "min" in rules and isinstance(val, (int, float)):
        if val < rules["min"]: errors.append(f"[{key}] {val} < min {rules['min']}")
    if "max" in rules and isinstance(val, (int, float)):
        if val > rules["max"]: errors.append(f"[{key}] {val} > max {rules['max']}")
    if "enum" in rules and val not in rules["enum"]:
        errors.append(f"[{key}] {val!r} not in {rules['enum']}")
    if "pattern" in rules and isinstance(val, str):
        if not re.search(rules["pattern"], val):
            errors.append(f"[{key}] doesn't match pattern {rules['pattern']!r}")
    if "items_type" in rules and isinstance(val, list):
        it = TYPE_MAP.get(rules["items_type"])
        for i, item in enumerate(val):
            if it and not isinstance(item, it):
                errors.append(f"[{key}][{i}] expected {rules['items_type']}, got {type(item).__name__}")

if errors:
    print(f"INVALID ({len(errors)} errors):")
    for e in errors: print(f"  {e}")
    sys.exit(1)
else:
    print("VALID"); sys.exit(0)
