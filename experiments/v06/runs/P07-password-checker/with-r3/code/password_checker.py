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

COMMON_PASSWORDS = [
    "password", "123456", "12345678", "123456789", "qwerty", "abc123",
    "password1", "111111", "123123", "admin", "letmein", "welcome",
    "iloveyou", "monkey", "dragon", "football", "baseball", "master",
    "sunshine", "princess", "login", "passw0rd", "starwars", "trustno1",
]

DEFAULT_POLICY = {
    "min_length": 12,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_symbols": True,
    "forbidden_passwords": COMMON_PASSWORDS,
}

BOOL_FIELDS = ("require_uppercase", "require_lowercase", "require_digits", "require_symbols")
KNOWN_FIELDS = ("min_length",) + BOOL_FIELDS + ("forbidden_passwords",)

# (rule name, policy flag, character set)
CLASSES = (
    ("uppercase", "require_uppercase", string.ascii_uppercase),
    ("lowercase", "require_lowercase", string.ascii_lowercase),
    ("digits", "require_digits", string.digits),
    ("symbols", "require_symbols", string.punctuation),
)


class PolicyError(Exception):
    pass


def validate_policy(policy):
    """Return a list of error messages (empty when the policy is valid)."""
    if not isinstance(policy, dict):
        return ["policy: must be a JSON object"]
    errors = []
    for key in policy:
        if key not in KNOWN_FIELDS:
            errors.append("%s: unknown field" % key)
    ml = policy.get("min_length")
    if "min_length" not in policy:
        errors.append("min_length: missing")
    elif not isinstance(ml, int) or isinstance(ml, bool) or ml < 1:
        errors.append("min_length: must be an integer >= 1")
    for f in BOOL_FIELDS:
        if f in policy and not isinstance(policy[f], bool):
            errors.append("%s: must be a boolean" % f)
    fp = policy.get("forbidden_passwords", [])
    if not isinstance(fp, list) or not all(isinstance(x, str) for x in fp):
        errors.append("forbidden_passwords: must be a list of strings")
    if not errors:
        needed = sum(1 for _, flag, _ in CLASSES if policy.get(flag, False))
        if ml < needed:
            errors.append("min_length: %d is smaller than the %d required character classes"
                          % (ml, needed))
    return errors


def load_policy(path=None):
    """Load a policy. An explicit path must exist; the default path may be absent."""
    explicit = path is not None
    path = path or DEFAULT_POLICY_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            policy = json.load(fh)
    except FileNotFoundError:
        if explicit:
            raise PolicyError("%s: file not found" % path)
        return dict(DEFAULT_POLICY)
    except (OSError, ValueError) as exc:
        raise PolicyError("%s: cannot read policy (%s)" % (path, exc))
    errors = validate_policy(policy)
    if errors:
        raise PolicyError("; ".join(errors))
    return policy


def shannon_entropy(password):
    """Total Shannon entropy in bits: length * per-character empirical entropy."""
    n = len(password)
    if n == 0:
        return 0.0
    h = -sum((c / n) * math.log2(c / n) for c in Counter(password).values())
    return h * n


def check_password(password, policy):
    """Return the list of failed rule names (empty when compliant)."""
    failed = []
    if len(password) < policy.get("min_length", 1):
        failed.append("min_length")
    for name, flag, chars in CLASSES:
        if policy.get(flag, False) and not any(c in chars for c in password):
            failed.append(name)
    forbidden = {p.lower() for p in policy.get("forbidden_passwords", [])}
    if password.lower() in forbidden:
        failed.append("forbidden")
    return failed


def generate_password(policy, length=None):
    """Generate a random password satisfying the policy."""
    errors = validate_policy(policy)
    if errors:
        raise PolicyError("; ".join(errors))
    min_length = policy["min_length"]
    if length is None:
        length = max(min_length, 16)
    if length < min_length:
        raise PolicyError("length: %d is smaller than min_length %d" % (length, min_length))
    required = [chars for _, flag, chars in CLASSES if policy.get(flag, False)]
    pool = "".join(required) or "".join(c for _, _, c in CLASSES)
    rng = secrets.SystemRandom()
    while True:
        chars = [secrets.choice(c) for c in required]
        chars += [secrets.choice(pool) for _ in range(length - len(chars))]
        rng.shuffle(chars)
        pw = "".join(chars)
        if not check_password(pw, policy):
            return pw


def _read_password(arg):
    if arg is not None and arg != "-":
        return arg
    return sys.stdin.readline().rstrip("\r\n")


def cmd_check(args):
    policy = load_policy(args.policy)
    pw = _read_password(args.password)
    failed = check_password(pw, policy)
    print("length: %d" % len(pw))
    print("entropy: %.2f bits" % shannon_entropy(pw))
    if failed:
        print("FAIL: %d rule(s) failed" % len(failed))
        for rule in failed:
            print("  - %s" % rule)
        return 1
    print("PASS: all rules satisfied")
    return 0


def cmd_generate(args):
    policy = load_policy(args.policy)
    if args.count < 1:
        raise PolicyError("count: must be >= 1")
    for _ in range(args.count):
        print(generate_password(policy, args.length))
    return 0


def cmd_validate(args):
    load_policy(args.policy or DEFAULT_POLICY_PATH)
    print("policy OK")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="password_checker",
                                     description="Password policy checker.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check", help="check a password against the policy")
    p.add_argument("password", nargs="?", help="password (omit or '-' to read from stdin)")
    p.add_argument("--policy", help="policy file (default: policy.json)")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("generate", help="generate random passwords satisfying the policy")
    p.add_argument("--policy", help="policy file (default: policy.json)")
    p.add_argument("--length", type=int, help="password length (default: max(min_length, 16))")
    p.add_argument("--count", type=int, default=1, help="how many passwords")
    p.set_defaults(func=cmd_generate)
    p = sub.add_parser("validate-policy", help="validate a policy file")
    p.add_argument("--policy", help="policy file (default: policy.json)")
    p.set_defaults(func=cmd_validate)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        return args.func(args)
    except PolicyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
