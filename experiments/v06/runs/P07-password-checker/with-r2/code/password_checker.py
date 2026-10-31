#!/usr/bin/env python3
"""Password policy checker: check, generate and validate-policy (stdlib only)."""
import argparse
import json
import math
import secrets
import string
import sys
from collections import Counter

DEFAULT_POLICY_PATH = "policy.json"
DEFAULTS = {
    "min_length": 8,
    "require_uppercase": False,
    "require_lowercase": False,
    "require_digits": False,
    "require_symbols": False,
    "forbidden_passwords": [],
}
BOOL_KEYS = ("require_uppercase", "require_lowercase", "require_digits", "require_symbols")
CLASSES = (
    ("require_uppercase", string.ascii_uppercase),
    ("require_lowercase", string.ascii_lowercase),
    ("require_digits", string.digits),
    ("require_symbols", string.punctuation),
)


class PolicyError(Exception):
    """Raised for unreadable or invalid policies."""


def validate_policy(data):
    """Return a list of problems (empty when the policy is well formed)."""
    if not isinstance(data, dict):
        return ["policy must be a JSON object"]
    problems = []
    for key in data:
        if key not in DEFAULTS:
            problems.append("unknown key: %s" % key)
    if "min_length" in data:
        v = data["min_length"]
        if isinstance(v, bool) or not isinstance(v, int):
            problems.append("min_length must be an integer")
        elif v < 1:
            problems.append("min_length must be >= 1")
    for key in BOOL_KEYS:
        if key in data and not isinstance(data[key], bool):
            problems.append("%s must be true or false" % key)
    if "forbidden_passwords" in data:
        v = data["forbidden_passwords"]
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            problems.append("forbidden_passwords must be a list of strings")
    if not problems:
        merged = dict(DEFAULTS, **data)
        needed = sum(1 for key, _ in CLASSES if merged[key])
        if merged["min_length"] < needed:
            problems.append(
                "min_length %d is smaller than the %d required character classes"
                % (merged["min_length"], needed)
            )
    return problems


def load_policy(path):
    """Load and validate a policy file; missing keys take defaults."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise PolicyError("cannot read policy %s: %s" % (path, exc.strerror or exc))
    except ValueError as exc:
        raise PolicyError("invalid JSON in %s: %s" % (path, exc))
    problems = validate_policy(data)
    if problems:
        raise PolicyError("; ".join(problems))
    return dict(DEFAULTS, **data)


def entropy_bits(password):
    """Shannon entropy in bits: length * per-character entropy of the frequencies."""
    n = len(password)
    if n == 0:
        return 0.0
    h = -sum((c / n) * math.log2(c / n) for c in Counter(password).values())
    return abs(h * n)


def failed_rules(password, policy):
    """Return a description of every rule the password violates."""
    failed = []
    if len(password) < policy["min_length"]:
        failed.append("minimum length %d (got %d)" % (policy["min_length"], len(password)))
    if policy["require_uppercase"] and not any(c in string.ascii_uppercase for c in password):
        failed.append("at least one uppercase letter")
    if policy["require_lowercase"] and not any(c in string.ascii_lowercase for c in password):
        failed.append("at least one lowercase letter")
    if policy["require_digits"] and not any(c in string.digits for c in password):
        failed.append("at least one digit")
    if policy["require_symbols"] and not any(c in string.punctuation for c in password):
        failed.append("at least one symbol")
    if password.lower() in {p.lower() for p in policy["forbidden_passwords"]}:
        failed.append("password is in the forbidden list")
    return failed


def generate_password(policy, length=None):
    """Generate a random password satisfying the policy (raises PolicyError)."""
    required = [chars for key, chars in CLASSES if policy[key]]
    if length is None:
        length = max(policy["min_length"], 16)
    if length < policy["min_length"]:
        raise PolicyError("length %d is below min_length %d" % (length, policy["min_length"]))
    if length < len(required):
        raise PolicyError("length %d cannot hold %d required classes" % (length, len(required)))
    pool = "".join(required) or "".join(c for _, c in CLASSES)
    for _ in range(1000):
        chars = [secrets.choice(c) for c in required]
        chars += [secrets.choice(pool) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        candidate = "".join(chars)
        if not failed_rules(candidate, policy):
            return candidate
    raise PolicyError("could not generate a password satisfying the policy")


def _load_or_exit(path):
    try:
        return load_policy(path)
    except PolicyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return None


def cmd_check(args):
    policy = _load_or_exit(args.policy)
    if policy is None:
        return 2
    password = args.password
    if password is None:
        password = sys.stdin.readline().rstrip("\r\n")
    failed = failed_rules(password, policy)
    print("Entropy: %.2f bits" % entropy_bits(password))
    if failed:
        print("FAIL: %d rule(s) failed" % len(failed))
        for rule in failed:
            print("  - %s" % rule)
        return 1
    print("OK: password satisfies the policy")
    return 0


def cmd_generate(args):
    policy = _load_or_exit(args.policy)
    if policy is None:
        return 2
    if args.count < 1:
        print("error: --count must be >= 1", file=sys.stderr)
        return 2
    try:
        for _ in range(args.count):
            print(generate_password(policy, args.length))
    except PolicyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


def cmd_validate_policy(args):
    try:
        load_policy(args.policy)
    except PolicyError as exc:
        print("invalid policy: %s" % exc, file=sys.stderr)
        return 2
    print("policy OK: %s" % args.policy)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="password_checker", description="Password policy checker")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check", help="check a password against the policy")
    p.add_argument("--password", help="password (default: first line of stdin)")
    p.add_argument("--policy", default=DEFAULT_POLICY_PATH)
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("generate", help="generate random passwords satisfying the policy")
    p.add_argument("--length", type=int)
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--policy", default=DEFAULT_POLICY_PATH)
    p.set_defaults(func=cmd_generate)
    p = sub.add_parser("validate-policy", help="validate a policy file")
    p.add_argument("--policy", default=DEFAULT_POLICY_PATH)
    p.set_defaults(func=cmd_validate_policy)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
