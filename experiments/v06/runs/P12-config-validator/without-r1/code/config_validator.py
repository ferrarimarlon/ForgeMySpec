#!/usr/bin/env python3
"""Validate a JSON config file against a JSON schema file.

Supported schema keywords: type, required, properties, enum, minimum, maximum,
minLength, maxLength, pattern, items (arrays), nested objects.

Usage: config_validator.py CONFIG.json SCHEMA.json
Exit codes: 0 valid, 1 validation errors, 2 usage/IO/schema errors.
"""
import argparse
import json
import re
import sys

TYPE_NAMES = ("string", "integer", "number", "boolean", "array", "object", "null")


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


def matches_type(value, expected):
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    raise ValueError("unknown type in schema: %r" % (expected,))


def join(path, key):
    return "%s.%s" % (path, key) if path else str(key)


def validate(value, schema, path, errors):
    """Append error strings for `value` against `schema` to `errors`."""
    where = path or "<root>"

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(matches_type(value, t) for t in types):
            errors.append("%s: expected type %s, got %s" % (where, " or ".join(types), type_name(value)))
            return  # further checks would be meaningless

    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: value %r not in enum %s" % (where, value, json.dumps(schema["enum"])))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: value %s is less than minimum %s" % (where, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: value %s is greater than maximum %s" % (where, value, schema["maximum"]))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: length %d is less than minLength %s" % (where, len(value), schema["minLength"]))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("%s: length %d is greater than maxLength %s" % (where, len(value), schema["maxLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: value %r does not match pattern %r" % (where, value, schema["pattern"]))

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append("%s: required field is missing" % join(path, name))
        for name, sub in props.items():
            if name in value:
                validate(value[name], sub, join(path, name), errors)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            validate(item, schema["items"], "%s[%d]" % (path, i) if path else "[%d]" % i, errors)


def load_json(filename, label):
    try:
        with open(filename, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        msg = "cannot read %s file: %s" % (label, e)
    except ValueError as e:  # JSONDecodeError and bad UTF-8
        msg = "invalid JSON in %s file %s: %s" % (label, filename, e)
    print("error: " + msg, file=sys.stderr)
    raise SystemExit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a JSON config against a JSON schema.")
    ap.add_argument("config", help="path to JSON config file")
    ap.add_argument("schema", help="path to JSON schema file")
    args = ap.parse_args(argv)

    config = load_json(args.config, "config")
    schema = load_json(args.schema, "schema")
    if not isinstance(schema, dict):
        print("error: schema must be a JSON object", file=sys.stderr)
        return 2

    errors = []
    try:
        validate(config, schema, "", errors)
    except (ValueError, re.error, TypeError) as e:
        print("error: invalid schema: %s" % e, file=sys.stderr)
        return 2

    if errors:
        print("%s: %d validation error(s)" % (args.config, len(errors)))
        for e in errors:
            print("  - " + e)
        return 1
    print("%s: valid" % args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
