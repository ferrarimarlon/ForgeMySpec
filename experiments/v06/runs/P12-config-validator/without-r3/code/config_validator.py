#!/usr/bin/env python3
"""Validate a JSON config file against a JSON schema file.

Usage: config_validator.py CONFIG.json SCHEMA.json

Supported schema keywords: type, required, properties, enum, minimum,
maximum, minLength, maxLength, pattern, items (for arrays).
Exit codes: 0 valid, 1 validation errors, 2 usage/IO/schema errors.
"""
import argparse
import json
import re
import sys

TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


def validate(value, schema, path, errors):
    """Append error strings for value against schema; path is dotted."""
    where = path or "<root>"
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        for n in names:
            if n not in TYPES:
                errors.append(f"{where}: unknown type '{n}' in schema")
                return
        if not any(TYPES[n](value) for n in names):
            errors.append(
                f"{where}: expected type {' or '.join(names)}, got {type_name(value)}"
            )
            return  # further checks are meaningless on the wrong type

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: value {value!r} not in enum {schema['enum']}")

    if TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: {value} is less than minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: {value} is greater than maximum {schema['maximum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(
                f"{where}: length {len(value)} is less than minLength {schema['minLength']}"
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(
                f"{where}: length {len(value)} is greater than maxLength {schema['maxLength']}"
            )
        if "pattern" in schema:
            try:
                if not re.search(schema["pattern"], value):
                    errors.append(
                        f"{where}: {value!r} does not match pattern {schema['pattern']!r}"
                    )
            except re.error as e:
                errors.append(f"{where}: invalid pattern in schema: {e}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path + '.' if path else ''}{name}: required field is missing")
        for name, sub in props.items():
            if name in value:
                validate(value[name], sub, f"{path}.{name}" if path else name, errors)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]", errors)


def load(path, label):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        msg = f"error: cannot read {label} file: {e}"
    except ValueError as e:  # JSONDecodeError and bad UTF-8
        msg = f"error: {label} file {path} is not valid JSON: {e}"
    print(msg, file=sys.stderr)
    sys.exit(2)


def main(argv=None):
    p = argparse.ArgumentParser(description="Validate a JSON config against a JSON schema.")
    p.add_argument("config", help="path to JSON config file")
    p.add_argument("schema", help="path to JSON schema file")
    args = p.parse_args(argv)

    config = load(args.config, "config")
    schema = load(args.schema, "schema")
    if not isinstance(schema, dict):
        print("error: schema must be a JSON object", file=sys.stderr)
        return 2

    errors = []
    validate(config, schema, "", errors)
    if errors:
        print(f"{len(errors)} validation error(s) in {args.config}:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{args.config}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
