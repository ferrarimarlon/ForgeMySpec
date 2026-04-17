#!/usr/bin/env python3
"""Config Validator CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: dot-notation nested keys, all validators independent, all errors reported.
"""
import argparse
import json
import re
import sys
from typing import Any, List, Optional


TYPE_MAP = {
    "string": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}


def resolve_key(config: dict, dotted_key: str) -> tuple:
    """Resolve dot-notation key into config. Returns (value, found: bool)."""
    parts = dotted_key.split(".")
    current = config
    for part in parts:
        if not isinstance(current, dict):
            return None, False
        if part not in current:
            return None, False
        current = current[part]
    return current, True


def validate_config(config: dict, schema: dict) -> List[str]:
    """Run all validators independently. Returns list of all errors."""
    errors = []

    for key, rules in schema.items():
        value, found = resolve_key(config, key)

        is_required = rules.get("required", False)
        if not found:
            if is_required:
                errors.append(f"[{key}] Required field is missing")
            continue  # Skip further checks if key absent

        expected_type_str = rules.get("type")
        if expected_type_str:
            expected_type = TYPE_MAP.get(expected_type_str)
            if expected_type is None:
                errors.append(f"[{key}] Schema error: unknown type '{expected_type_str}'")
            else:
                # Strict type check: no coercion
                if not isinstance(value, expected_type):
                    # Special case: bool is subclass of int in Python — reject bool for int
                    if expected_type == int and isinstance(value, bool):
                        errors.append(
                            f"[{key}] Type error: expected int, got bool (value: {value!r})"
                        )
                    elif expected_type == float and isinstance(value, bool):
                        errors.append(
                            f"[{key}] Type error: expected float, got bool (value: {value!r})"
                        )
                    else:
                        errors.append(
                            f"[{key}] Type error: expected {expected_type_str}, "
                            f"got {type(value).__name__} (value: {value!r})"
                        )

        # min/max (for numeric)
        if "min" in rules and isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < rules["min"]:
                errors.append(f"[{key}] Value {value} is below minimum {rules['min']}")
        if "max" in rules and isinstance(value, (int, float)) and not isinstance(value, bool):
            if value > rules["max"]:
                errors.append(f"[{key}] Value {value} exceeds maximum {rules['max']}")

        # enum
        if "enum" in rules:
            if value not in rules["enum"]:
                errors.append(f"[{key}] Value {value!r} not in allowed values: {rules['enum']}")

        # pattern (strings only)
        if "pattern" in rules and isinstance(value, str):
            if not re.search(rules["pattern"], value):
                errors.append(
                    f"[{key}] Value {value!r} does not match pattern '{rules['pattern']}'"
                )

        # items_type (lists only)
        if "items_type" in rules and isinstance(value, list):
            item_type_str = rules["items_type"]
            item_type = TYPE_MAP.get(item_type_str)
            if item_type is None:
                errors.append(f"[{key}] Schema error: unknown items_type '{item_type_str}'")
            else:
                for i, item in enumerate(value):
                    if not isinstance(item, item_type):
                        errors.append(
                            f"[{key}][{i}] items_type error: expected {item_type_str}, "
                            f"got {type(item).__name__} (value: {item!r})"
                        )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Config Validator CLI")
    sub = parser.add_subparsers(dest="command")

    p_val = sub.add_parser("validate", help="Validate config against schema")
    p_val.add_argument("config", help="Config JSON file")
    p_val.add_argument("schema", help="Schema JSON file")

    args = parser.parse_args()

    if args.command == "validate":
        try:
            with open(args.config) as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            with open(args.schema) as f:
                schema = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading schema: {e}", file=sys.stderr)
            sys.exit(1)

        errors = validate_config(config, schema)
        if errors:
            print(f"Config INVALID — {len(errors)} error(s):")
            for err in errors:
                print(f"  {err}")
            sys.exit(1)
        else:
            print("Config is VALID.")
            sys.exit(0)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
