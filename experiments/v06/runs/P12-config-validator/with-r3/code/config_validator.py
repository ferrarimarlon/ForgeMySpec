#!/usr/bin/env python3
"""Validate a JSON config file against a JSON schema file (stdlib only).

Usage: python3 config_validator.py <schema.json> <config.json>
Exit codes: 0 valid, 1 validation errors, 2 usage / unreadable file / malformed JSON.
"""
import json
import re
import sys

_TYPE_NAMES = ("string", "integer", "number", "boolean", "array", "object")


def _is_type(value, name):
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
    return True  # unknown type names are ignored


def _json_type(value):
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


def _join(path, key):
    return "%s.%s" % (path, key) if path else key


def _validate(value, schema, path, errors):
    if not isinstance(schema, dict):
        return
    where = path or "<root>"
    expected = schema.get("type")
    if expected in _TYPE_NAMES and not _is_type(value, expected):
        errors.append("%s: expected %s, got %s" % (where, expected, _json_type(value)))
        return

    if "enum" in schema and isinstance(schema["enum"], list):
        if not any(value == e and type(value) is type(e) for e in schema["enum"]):
            errors.append("%s: value %s not in enum %s"
                          % (where, json.dumps(value), json.dumps(schema["enum"])))

    if _is_type(value, "number"):
        lo, hi = schema.get("minimum"), schema.get("maximum")
        if isinstance(lo, (int, float)) and value < lo:
            errors.append("%s: value %s is less than minimum %s" % (where, value, lo))
        if isinstance(hi, (int, float)) and value > hi:
            errors.append("%s: value %s is greater than maximum %s" % (where, value, hi))

    if isinstance(value, str):
        lo, hi = schema.get("minLength"), schema.get("maxLength")
        if isinstance(lo, int) and len(value) < lo:
            errors.append("%s: length %d is less than minLength %d" % (where, len(value), lo))
        if isinstance(hi, int) and len(value) > hi:
            errors.append("%s: length %d is greater than maxLength %d" % (where, len(value), hi))
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                if re.search(pattern, value) is None:
                    errors.append("%s: value %s does not match pattern %s"
                                  % (where, json.dumps(value), json.dumps(pattern)))
            except re.error as exc:
                errors.append("%s: invalid pattern %s (%s)" % (where, json.dumps(pattern), exc))

    if isinstance(value, dict):
        props = schema.get("properties")
        props = props if isinstance(props, dict) else {}
        required = schema.get("required")
        for name in required if isinstance(required, list) else []:
            if name not in value:
                errors.append("%s: required field missing" % _join(path, name))
        for name, sub in props.items():
            if name in value:
                _validate(value[name], sub, _join(path, name), errors)


def validate(config, schema):
    """Return a list of error strings (empty when the config is valid)."""
    errors = []
    _validate(config, schema, "", errors)
    return errors


class _LoadError(Exception):
    pass


def _load(path, label):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise _LoadError("cannot read %s file %s: %s" % (label, path, exc.strerror or exc))
    except ValueError as exc:
        raise _LoadError("%s file %s is not valid JSON: %s" % (label, path, exc))


def _fail(message):
    print("error: " + message, file=sys.stderr)
    return 2


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        return _fail("usage: config_validator.py <schema.json> <config.json>")
    try:
        schema = _load(argv[0], "schema")
        config = _load(argv[1], "config")
    except _LoadError as exc:
        return _fail(str(exc))
    errors = validate(config, schema)
    for line in errors:
        print(line)
    if errors:
        print("%d error(s) found" % len(errors), file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
