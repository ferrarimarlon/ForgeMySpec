#!/usr/bin/env python3
"""Password policy checker: check, generate, validate-policy. Stdlib only."""

import argparse
import getpass
import json
import math
import secrets
import string
import sys
from collections import Counter

SYMBOLS = string.punctuation

DEFAULT_POLICY = {
    "min_length": 12,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_symbols": True,
    "forbidden_passwords": [
        "password", "password1", "password123", "123456", "12345678",
        "123456789", "qwerty", "qwerty123", "abc123", "letmein", "welcome",
        "admin", "iloveyou", "monkey", "dragon", "football", "111111",
        "login", "passw0rd", "p@ssw0rd", "changeme",
    ],
}

# key -> (type, description)
SCHEMA = {
    "min_length": int,
    "max_length": int,
    "require_uppercase": bool,
    "require_lowercase": bool,
    "require_digits": bool,
    "require_symbols": bool,
    "forbidden_passwords": list,
}


def validate_policy(policy):
    """Return a list of problems with the policy (empty if valid)."""
    errors = []
    if not isinstance(policy, dict):
        return ["policy must be a JSON object"]
    for key, value in policy.items():
        if key not in SCHEMA:
            errors.append(f"unknown key: {key!r}")
            continue
        expected = SCHEMA[key]
        # bool is a subclass of int; reject it for integer fields
        if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
            errors.append(f"{key} must be an integer")
        elif expected is not int and not isinstance(value, expected):
            errors.append(f"{key} must be {expected.__name__}")
    if errors:
        return errors
    if "min_length" in policy and policy["min_length"] < 1:
        errors.append("min_length must be >= 1")
    if "max_length" in policy and policy["max_length"] < 1:
        errors.append("max_length must be >= 1")
    merged = {**DEFAULT_POLICY, **policy}
    if merged.get("max_length") is not None and merged["max_length"] < merged["min_length"]:
        errors.append("max_length must be >= min_length")
    if not all(isinstance(x, str) for x in merged["forbidden_passwords"]):
        errors.append("forbidden_passwords must contain only strings")
    required = sum(merged[k] for k in (
        "require_uppercase", "require_lowercase", "require_digits", "require_symbols"))
    if merged.get("max_length") is not None and merged["max_length"] < required:
        errors.append(f"max_length too small to satisfy {required} required character classes")
    if merged["min_length"] < required and not errors:
        pass  # generator lengthens as needed; checker still enforces classes
    return errors


def load_policy(path):
    """Load policy from path, merged over defaults. Raises ValueError on problems."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"policy file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path}: {e}")
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e}")
    errors = validate_policy(data)
    if errors:
        raise ValueError("; ".join(errors))
    return {**DEFAULT_POLICY, **data}


def get_policy(path):
    """Use the given path, else policy.json if it exists, else defaults."""
    import os
    if path:
        return load_policy(path)
    if os.path.exists("policy.json"):
        return load_policy("policy.json")
    return dict(DEFAULT_POLICY)


def is_symbol(c):
    return not c.isalnum() and not c.isspace() and c.isascii() or (
        not c.isascii() and not c.isalnum() and not c.isspace())


def check_password(password, policy):
    """Return list of failure messages."""
    failures = []
    if len(password) < policy["min_length"]:
        failures.append(f"too short: {len(password)} < minimum {policy['min_length']}")
    mx = policy.get("max_length")
    if mx is not None and len(password) > mx:
        failures.append(f"too long: {len(password)} > maximum {mx}")
    if policy["require_uppercase"] and not any(c.isupper() for c in password):
        failures.append("missing an uppercase letter")
    if policy["require_lowercase"] and not any(c.islower() for c in password):
        failures.append("missing a lowercase letter")
    if policy["require_digits"] and not any(c.isdigit() for c in password):
        failures.append("missing a digit")
    if policy["require_symbols"] and not any(is_symbol(c) for c in password):
        failures.append("missing a symbol")
    forbidden = {p.lower() for p in policy["forbidden_passwords"]}
    if password.lower() in forbidden:
        failures.append("is a forbidden common password")
    return failures


def shannon_entropy(password):
    """Return (bits per character, total bits) from observed character frequencies."""
    if not password:
        return 0.0, 0.0
    n = len(password)
    per_char = -sum((c / n) * math.log2(c / n) for c in Counter(password).values())
    return per_char, per_char * n


def generate_password(policy, length=None):
    """Generate a random password satisfying the policy."""
    pools = []
    if policy["require_uppercase"]:
        pools.append(string.ascii_uppercase)
    if policy["require_lowercase"]:
        pools.append(string.ascii_lowercase)
    if policy["require_digits"]:
        pools.append(string.digits)
    if policy["require_symbols"]:
        pools.append(SYMBOLS)
    alphabet = "".join(pools) or (string.ascii_letters + string.digits)
    mx = policy.get("max_length")
    if length is None:
        length = max(policy["min_length"], 16 if mx is None else min(16, mx))
    if length < policy["min_length"] or (mx is not None and length > mx):
        raise ValueError("requested length conflicts with policy length limits")
    if length < len(pools):
        raise ValueError("length too small to include every required character class")
    forbidden = {p.lower() for p in policy["forbidden_passwords"]}
    while True:
        chars = [secrets.choice(p) for p in pools]
        chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        pw = "".join(chars)
        if pw.lower() not in forbidden and not check_password(pw, policy):
            return pw


def cmd_check(args):
    policy = get_policy(args.policy)
    password = args.password
    if password is None:
        password = getpass.getpass("Password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
    failures = check_password(password, policy)
    per_char, total = shannon_entropy(password)
    if args.json:
        print(json.dumps({"passed": not failures, "failures": failures,
                          "length": len(password),
                          "entropy_bits_per_char": round(per_char, 3),
                          "entropy_bits": round(total, 2)}, indent=2))
    else:
        print(f"Result: {'PASS' if not failures else 'FAIL'}")
        for f in failures:
            print(f"  - {f}")
        print(f"Length: {len(password)}")
        print(f"Shannon entropy: {per_char:.3f} bits/char, {total:.2f} bits total")
    return 0 if not failures else 1


def cmd_generate(args):
    policy = get_policy(args.policy)
    for _ in range(args.count):
        pw = generate_password(policy, args.length)
        if args.show_entropy:
            print(f"{pw}\t{shannon_entropy(pw)[1]:.2f} bits")
        else:
            print(pw)
    return 0


def cmd_validate(args):
    path = args.file or "policy.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: {path}: {e}", file=sys.stderr)
        return 2
    errors = validate_policy(data)
    if errors:
        print(f"{path}: INVALID")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{path}: valid")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Password policy checker and generator")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check a password against the policy")
    c.add_argument("password", nargs="?",
                   help="password (omit to be prompted / read from stdin; avoids shell history)")
    c.add_argument("-p", "--policy", help="policy file (default: ./policy.json if present)")
    c.add_argument("--json", action="store_true", help="JSON output")
    c.set_defaults(func=cmd_check)

    g = sub.add_parser("generate", help="generate random passwords satisfying the policy")
    g.add_argument("-p", "--policy", help="policy file (default: ./policy.json if present)")
    g.add_argument("-l", "--length", type=int, help="password length")
    g.add_argument("-n", "--count", type=int, default=1, help="how many to generate")
    g.add_argument("--show-entropy", action="store_true", help="print entropy next to each password")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate-policy", help="validate a policy file")
    v.add_argument("file", nargs="?", help="policy file (default: policy.json)")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
