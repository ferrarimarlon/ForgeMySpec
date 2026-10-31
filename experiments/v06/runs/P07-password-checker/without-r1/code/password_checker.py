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
        "password", "123456", "12345678", "qwerty", "abc123", "letmein",
        "welcome", "admin", "iloveyou", "monkey", "dragon", "football",
        "password1", "passw0rd", "123456789", "111111", "login", "master",
    ],
}

# key -> (expected type, description)
SCHEMA = {
    "min_length": int,
    "max_length": int,
    "require_uppercase": bool,
    "require_lowercase": bool,
    "require_digits": bool,
    "require_symbols": bool,
    "forbidden_passwords": list,
    "min_entropy": (int, float),
}

CLASSES = [
    ("require_uppercase", string.ascii_uppercase, "an uppercase letter"),
    ("require_lowercase", string.ascii_lowercase, "a lowercase letter"),
    ("require_digits", string.digits, "a digit"),
    ("require_symbols", SYMBOLS, "a symbol"),
]


def validate_policy(policy):
    """Return a list of problems with the policy (empty if valid)."""
    if not isinstance(policy, dict):
        return ["policy must be a JSON object"]
    errors = []
    for key, value in policy.items():
        if key not in SCHEMA:
            errors.append(f"unknown key: {key!r}")
            continue
        expected = SCHEMA[key]
        # bool is a subclass of int; reject it for numeric fields
        if (expected is not bool and isinstance(value, bool)) or not isinstance(value, expected):
            names = expected.__name__ if isinstance(expected, type) else "number"
            errors.append(f"{key}: expected {names}, got {type(value).__name__}")
    if errors:
        return errors
    if "min_length" in policy and policy["min_length"] < 1:
        errors.append("min_length must be >= 1")
    if "max_length" in policy:
        if policy["max_length"] < 1:
            errors.append("max_length must be >= 1")
        elif policy["max_length"] < policy.get("min_length", 0):
            errors.append("max_length must be >= min_length")
    if "min_entropy" in policy and policy["min_entropy"] < 0:
        errors.append("min_entropy must be >= 0")
    if "forbidden_passwords" in policy:
        if not all(isinstance(p, str) for p in policy["forbidden_passwords"]):
            errors.append("forbidden_passwords must contain only strings")
    required = sum(1 for k, _, _ in CLASSES if policy.get(k))
    if required and "max_length" in policy and policy["max_length"] < required:
        errors.append("max_length is too small to include every required character class")
    return errors


def load_policy(path):
    """Load policy from path (or defaults if None). Raises ValueError on problems."""
    if path is None:
        return dict(DEFAULT_POLICY)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ValueError(f"cannot read policy file: {e.strerror or e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path}: {e}")
    errors = validate_policy(data)
    if errors:
        raise ValueError("invalid policy:\n  " + "\n  ".join(errors))
    merged = dict(DEFAULT_POLICY)
    merged.update(data)
    return merged


def entropy_bits(password):
    """Total Shannon entropy in bits: per-symbol entropy of the empirical
    character distribution times the length."""
    n = len(password)
    if n == 0:
        return 0.0
    counts = Counter(password)
    per_char = -sum(c / n * math.log2(c / n) for c in counts.values())
    return per_char * n


def pool_entropy_bits(password):
    """Upper-bound estimate: length * log2(size of character pool used)."""
    pool = 0
    for _, chars, _ in CLASSES:
        if any(ch in chars for ch in password):
            pool += len(chars)
    if any(ch not in string.ascii_letters + string.digits + SYMBOLS for ch in password):
        pool += 32  # other/unicode characters, rough allowance
    return len(password) * math.log2(pool) if pool else 0.0


def check_password(password, policy):
    """Return a list of failure messages (empty if the password passes)."""
    failures = []
    if len(password) < policy["min_length"]:
        failures.append(f"too short: {len(password)} characters, minimum is {policy['min_length']}")
    if "max_length" in policy and len(password) > policy["max_length"]:
        failures.append(f"too long: {len(password)} characters, maximum is {policy['max_length']}")
    for key, chars, label in CLASSES:
        if policy.get(key) and not any(ch in chars for ch in password):
            failures.append(f"missing {label}")
    lowered = password.lower()
    for bad in policy.get("forbidden_passwords", []):
        if bad and bad.lower() == lowered:
            failures.append("password is on the forbidden list")
            break
    else:
        for bad in policy.get("forbidden_passwords", []):
            if len(bad) >= 4 and bad.lower() in lowered:
                failures.append(f"contains forbidden password {bad!r}")
                break
    if "min_entropy" in policy and entropy_bits(password) < policy["min_entropy"]:
        failures.append(
            f"entropy too low: {entropy_bits(password):.1f} bits, minimum is {policy['min_entropy']}")
    return failures


def generate_password(policy, length=None):
    """Generate a random password satisfying the policy."""
    required = [chars for key, chars, _ in CLASSES if policy.get(key)]
    min_len = max(policy["min_length"], len(required), 1)
    max_len = policy.get("max_length")
    if length is None:
        length = max(min_len, 16)
        if max_len is not None:
            length = min(length, max_len)
    if length < min_len or (max_len is not None and length > max_len):
        raise ValueError(f"length {length} conflicts with policy "
                         f"(min {min_len}, max {max_len if max_len else 'none'})")
    alphabet = "".join(required) or (string.ascii_letters + string.digits + SYMBOLS)
    forbidden = [b.lower() for b in policy.get("forbidden_passwords", []) if b]
    for _ in range(1000):
        chars = [secrets.choice(c) for c in required]
        chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        pw = "".join(chars)
        if not check_password(pw, policy) and not any(f in pw.lower() for f in forbidden):
            return pw
    raise ValueError("could not generate a password satisfying the policy")


def cmd_check(args):
    policy = load_policy(args.policy)
    if args.password is not None:
        password = args.password
    elif not sys.stdin.isatty():
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Password: ")
    failures = check_password(password, policy)
    bits = entropy_bits(password)
    if args.json:
        print(json.dumps({"passed": not failures, "failures": failures,
                          "entropy_bits": round(bits, 2),
                          "pool_entropy_bits": round(pool_entropy_bits(password), 2),
                          "length": len(password)}, indent=2))
    else:
        print(f"Length:  {len(password)}")
        print(f"Entropy: {bits:.2f} bits (Shannon, empirical)")
        print(f"Pool:    {pool_entropy_bits(password):.2f} bits (length * log2(pool))")
        if failures:
            print(f"FAIL: {len(failures)} rule(s) failed")
            for f in failures:
                print(f"  - {f}")
        else:
            print("PASS: all rules satisfied")
    return 1 if failures else 0


def cmd_generate(args):
    policy = load_policy(args.policy)
    if args.count < 1:
        raise ValueError("--count must be >= 1")
    for _ in range(args.count):
        pw = generate_password(policy, args.length)
        if args.show_entropy:
            print(f"{pw}\t{entropy_bits(pw):.2f} bits")
        else:
            print(pw)
    return 0


def cmd_validate_policy(args):
    path = args.policy or "policy.json"
    try:
        load_policy(path)
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {path} is a valid policy")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Password policy checker and generator.")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check a password against the policy")
    c.add_argument("password", nargs="?",
                   help="password (omit to read from stdin or prompt; avoids shell history)")
    c.add_argument("-p", "--policy", help="path to policy JSON (default: built-in policy)")
    c.add_argument("--json", action="store_true", help="output JSON")
    c.set_defaults(func=cmd_check)

    g = sub.add_parser("generate", help="generate random passwords satisfying the policy")
    g.add_argument("-p", "--policy", help="path to policy JSON (default: built-in policy)")
    g.add_argument("-l", "--length", type=int, help="password length")
    g.add_argument("-n", "--count", type=int, default=1, help="how many to generate")
    g.add_argument("--show-entropy", action="store_true", help="print entropy next to each")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate-policy", help="validate a policy JSON file")
    v.add_argument("policy", nargs="?", help="path to policy file (default: policy.json)")
    v.set_defaults(func=cmd_validate_policy)
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
