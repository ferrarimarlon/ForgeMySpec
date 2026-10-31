#!/usr/bin/env python3
"""Validate a JSON config file against a JSON schema file (stdlib only).

Usage: config_validator.py CONFIG.json SCHEMA.json
Exit codes: 0 valid, 1 validation errors, 2 usage or unreadable/invalid input.
"""
import json
import re
import sys

TYPES = ("string", "integer", "number", "boolean", "array", "object")


def _type_ok(value, name):
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return False


def _enum_ok(value, options):
    # bool and int are distinct values (True != 1 for enum purposes)
    return any(o == value and isinstance(o, bool) == isinstance(value, bool)
               for o in options)


def _join(path, key):
    return "%s.%s" % (path, key) if path else key


def _validate_value(value, schema, path, errors):
    label = path or "<root>"
    if not isinstance(schema, dict):
        return
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, n) for n in names):
            errors.append("%s: expected type %s, got %s"
                          % (label, "/".join(names), _describe(value)))
            return
    if "enum" in schema and not _enum_ok(value, schema["enum"]):
        errors.append("%s: value %r not in enum %r" % (label, value, schema["enum"]))
    if _type_ok(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: value %r is less than minimum %r"
                          % (label, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: value %r is greater than maximum %r"
                          % (label, value, schema["maximum"]))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: length %d is less than minLength %d"
                          % (label, len(value), schema["minLength"]))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("%s: length %d is greater than maxLength %d"
                          % (label, len(value), schema["maxLength"]))
        if "pattern" in schema:
            try:
                matched = re.search(schema["pattern"], value) is not None
            except re.error as exc:
                errors.append("%s: invalid pattern %r (%s)" % (label, schema["pattern"], exc))
                matched = True
            if not matched:
                errors.append("%s: value %r does not match pattern %r"
                              % (label, value, schema["pattern"]))
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append("%s: required field is missing" % _join(path, name))
        for name, sub in (schema.get("properties") or {}).items():
            if name in value:
                _validate_value(value[name], sub, _join(path, name), errors)


def _describe(value):
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
    if isinstance(value, dict):
        return "object"
    return "null"


def validate(config, schema):
    """Return the list of all error messages (empty when valid)."""
    errors = []
    _validate_value(config, schema, "", errors)
    return errors


def _load(path, what):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise SystemExit_(2, "error: cannot read %s file %s: %s" % (what, path, exc.strerror))
    except ValueError as exc:
        raise SystemExit_(2, "error: invalid JSON in %s file %s: %s" % (what, path, exc))


class SystemExit_(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: config_validator.py CONFIG.json SCHEMA.json", file=sys.stderr)
        return 2
    try:
        config = _load(argv[0], "config")
        schema = _load(argv[1], "schema")
    except SystemExit_ as exc:
        print(exc.message, file=sys.stderr)
        return exc.code
    errors = validate(config, schema)
    for line in errors:
        print(line)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
