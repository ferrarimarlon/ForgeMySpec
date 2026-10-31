#!/usr/bin/env python3
"""Validate a JSON config file against a JSON schema file.

Supported schema keywords: type, required, properties, enum, minimum, maximum,
minLength, maxLength, pattern, items. Nested errors use dot notation
(e.g. "server.port"), with array indices as "[n]".

Usage: config_validator.py CONFIG.json SCHEMA.json
Exit codes: 0 valid, 1 validation errors, 2 usage/IO/schema error.
"""
import argparse
import json
import re
import sys

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def join(path, key):
    return f"{path}.{key}" if path else str(key)


def validate(value, schema, path="", errors=None):
    """Return a list of error strings for value against schema."""
    if errors is None:
        errors = []
    where = path or "<root>"

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        for t in types:
            if t not in TYPE_CHECKS:
                raise ValueError(f"unknown type {t!r} in schema at {where}")
        if not any(TYPE_CHECKS[t](value) for t in types):
            errors.append(
                f"{where}: expected {' or '.join(types)}, got {type_name(value)}"
            )
            return errors  # further checks would be meaningless

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: must be one of {schema['enum']!r}, got {value!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
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
                ok = re.search(schema["pattern"], value) is not None
            except re.error as e:
                raise ValueError(f"invalid regex at {where}: {e}")
            if not ok:
                errors.append(
                    f"{where}: {value!r} does not match pattern {schema['pattern']!r}"
                )

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{join(path, key)}: required field is missing")
        for key, sub in props.items():
            if key in value:
                validate(value[key], sub, join(path, key), errors)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]", errors)

    return errors


def load_json(filename, label):
    try:
        with open(filename, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        sys.exit_msg = f"error: cannot read {label} file: {e}"
    except json.JSONDecodeError as e:
        sys.exit_msg = f"error: {label} file {filename} is not valid JSON: {e}"
    print(sys.exit_msg, file=sys.stderr)
    sys.exit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("config", help="JSON config file to validate")
    parser.add_argument("schema", help="JSON schema file")
    args = parser.parse_args(argv)

    config = load_json(args.config, "config")
    schema = load_json(args.schema, "schema")
    if not isinstance(schema, dict):
        print("error: schema must be a JSON object", file=sys.stderr)
        return 2

    try:
        errors = validate(config, schema)
    except ValueError as e:
        print(f"error: bad schema: {e}", file=sys.stderr)
        return 2

    if errors:
        print(f"{args.config}: {len(errors)} validation error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{args.config}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
