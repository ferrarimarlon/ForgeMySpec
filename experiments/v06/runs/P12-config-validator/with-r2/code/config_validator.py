#!/usr/bin/env python3
"""Validate a JSON config file against a JSON schema file (small subset).

Usage: python3 config_validator.py <config.json> <schema.json>
Exit codes: 0 valid, 1 validation errors, 2 usage / file / JSON problems.
"""
import json
import re
import sys

_TYPE_NAMES = ("string", "integer", "number", "boolean", "array", "object")


def _type_ok(value, name):
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return True


def _type_of(value):
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _join(path, key):
    return f"{path}.{key}" if path else str(key)


def _validate(value, schema, path, errors):
    label = path or "<root>"
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, n) for n in names):
            errors.append(
                f"{label}: expected type {'/'.join(names)}, got {_type_of(value)}"
            )
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{label}: value {json.dumps(value)} not in enum {json.dumps(schema['enum'])}")

    if _type_ok(value, "number") and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{label}: value {value} is less than minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{label}: value {value} is greater than maximum {schema['maximum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{label}: length {len(value)} is less than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{label}: length {len(value)} is greater than maxLength {schema['maxLength']}")
        if "pattern" in schema:
            try:
                matched = re.search(schema["pattern"], value) is not None
            except re.error as exc:
                errors.append(f"{label}: invalid pattern {schema['pattern']!r} ({exc})")
            else:
                if not matched:
                    errors.append(f"{label}: value {json.dumps(value)} does not match pattern {schema['pattern']!r}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{_join(path, key)}: required field is missing")
        for key, sub in schema.get("properties", {}).items():
            if key in value and isinstance(sub, dict):
                _validate(value[key], sub, _join(path, key), errors)


def validate(config, schema):
    """Return the list of all error messages (empty when valid)."""
    errors = []
    _validate(config, schema, "", errors)
    return errors


def _load(path, what):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        print(f"error: cannot read {what} file {path}: {exc.strerror}", file=sys.stderr)
    except ValueError as exc:
        print(f"error: {what} file {path} is not valid JSON: {exc}", file=sys.stderr)
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: config_validator.py <config.json> <schema.json>", file=sys.stderr)
        return 2
    config = _load(argv[0], "config")
    if config is None and not _file_is_json_null(argv[0]):
        return 2
    schema = _load(argv[1], "schema")
    if not isinstance(schema, dict):
        if schema is not None:
            print("error: schema must be a JSON object", file=sys.stderr)
        return 2
    errors = validate(config, schema)
    if errors:
        for line in errors:
            print(line)
        print(f"{len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


def _file_is_json_null(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh) is None
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    sys.exit(main())
