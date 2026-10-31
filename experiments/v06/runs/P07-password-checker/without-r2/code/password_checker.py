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
        "password", "123456", "12345678", "123456789", "qwerty", "abc123",
        "letmein", "welcome", "admin", "iloveyou", "monkey", "dragon",
        "football", "password1", "passw0rd", "p@ssw0rd", "qwerty123",
        "111111", "000000", "changeme",
    ],
    "forbid_contains_common": True,
    "symbols": SYMBOLS,
}

SCHEMA = {
    "min_length": int,
    "require_uppercase": bool,
    "require_lowercase": bool,
    "require_digits": bool,
    "require_symbols": bool,
    "forbidden_passwords": list,
    "forbid_contains_common": bool,
    "symbols": str,
}


def validate_policy(policy):
    """Return a list of problems with a policy dict (empty if valid)."""
    errors = []
    if not isinstance(policy, dict):
        return ["policy must be a JSON object"]
    for key, value in policy.items():
        if key not in SCHEMA:
            errors.append(f"unknown key '{key}'")
            continue
        expected = SCHEMA[key]
        # bool is a subclass of int; reject it for int fields
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            errors.append(f"'{key}' must be of type {expected.__name__}")
    if errors:
        return errors
    if "min_length" in policy and policy["min_length"] < 1:
        errors.append("'min_length' must be >= 1")
    if "forbidden_passwords" in policy and not all(
        isinstance(x, str) for x in policy["forbidden_passwords"]
    ):
        errors.append("'forbidden_passwords' must contain only strings")
    if "symbols" in policy and not policy["symbols"] and policy.get("require_symbols", True):
        errors.append("'symbols' must be non-empty when require_symbols is true")
    merged = {**DEFAULT_POLICY, **policy}
    required = sum(merged[k] for k in (
        "require_uppercase", "require_lowercase", "require_digits", "require_symbols"))
    if merged["min_length"] < required and not errors:
        # Still satisfiable (generate extends length), but flag as inconsistent.
        errors.append(
            f"'min_length' ({merged['min_length']}) is less than the number of "
            f"required character classes ({required})")
    return errors


def load_policy(path):
    """Load policy from path (merged over defaults). Raises ValueError on problems."""
    if path is None:
        return dict(DEFAULT_POLICY)
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
        raise ValueError("invalid policy: " + "; ".join(errors))
    return {**DEFAULT_POLICY, **data}


def entropy_bits(password):
    """Total Shannon entropy in bits: per-character entropy of the password's
    own character distribution times its length."""
    if not password:
        return 0.0
    n = len(password)
    counts = Counter(password)
    per_char = -sum(c / n * math.log2(c / n) for c in counts.values())
    return per_char * n


def pool_entropy_bits(password, policy):
    """Theoretical entropy: length * log2(size of character pool used)."""
    if not password:
        return 0.0
    pool = 0
    if any(c.islower() for c in password):
        pool += 26
    if any(c.isupper() for c in password):
        pool += 26
    if any(c.isdigit() for c in password):
        pool += 10
    if any(c in policy["symbols"] for c in password):
        pool += len(set(policy["symbols"]))
    if any(not (c.isalnum() or c in policy["symbols"]) for c in password):
        pool += 1
    return len(password) * math.log2(pool) if pool > 1 else 0.0


def check_password(password, policy):
    """Return a list of failed-rule messages (empty if the password passes)."""
    failures = []
    if len(password) < policy["min_length"]:
        failures.append(
            f"too short: {len(password)} characters, need at least {policy['min_length']}")
    if policy["require_uppercase"] and not any(c.isupper() for c in password):
        failures.append("missing an uppercase letter")
    if policy["require_lowercase"] and not any(c.islower() for c in password):
        failures.append("missing a lowercase letter")
    if policy["require_digits"] and not any(c.isdigit() for c in password):
        failures.append("missing a digit")
    if policy["require_symbols"] and not any(c in policy["symbols"] for c in password):
        failures.append("missing a symbol")
    lowered = password.lower()
    forbidden = [w.lower() for w in policy["forbidden_passwords"] if w]
    if lowered in forbidden:
        failures.append("is a forbidden common password")
    elif policy["forbid_contains_common"]:
        hits = sorted({w for w in forbidden if len(w) >= 4 and w in lowered})
        if hits:
            failures.append("contains forbidden common password(s): " + ", ".join(hits))
    return failures


def generate_password(policy, length=None):
    """Generate a random password satisfying the policy."""
    rng = secrets.SystemRandom()
    pools = []
    if policy["require_uppercase"]:
        pools.append(string.ascii_uppercase)
    if policy["require_lowercase"]:
        pools.append(string.ascii_lowercase)
    if policy["require_digits"]:
        pools.append(string.digits)
    if policy["require_symbols"]:
        pools.append(policy["symbols"])
    if not pools:
        pools = [string.ascii_letters + string.digits]
    length = max(length or policy["min_length"], policy["min_length"], len(pools))
    alphabet = "".join(pools)
    for _ in range(1000):
        chars = [secrets.choice(p) for p in pools]
        chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
        rng.shuffle(chars)
        pw = "".join(chars)
        if not check_password(pw, policy):
            return pw
    raise RuntimeError("could not generate a password satisfying the policy")


def cmd_check(args):
    policy = load_policy(args.policy)
    password = args.password
    if password is None:
        password = getpass.getpass("Password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
    failures = check_password(password, policy)
    bits = entropy_bits(password)
    pool_bits = pool_entropy_bits(password, policy)
    if args.json:
        print(json.dumps({
            "passed": not failures,
            "failures": failures,
            "entropy_bits": round(bits, 2),
            "pool_entropy_bits": round(pool_bits, 2),
        }, indent=2))
    else:
        print(f"Length: {len(password)}")
        print(f"Shannon entropy: {bits:.2f} bits ({pool_bits:.2f} bits by character pool)")
        if failures:
            print("FAIL")
            for f in failures:
                print(f"  - {f}")
        else:
            print("PASS")
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
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"error: policy file not found: {path}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: cannot load {path}: {e}", file=sys.stderr)
        return 2
    errors = validate_policy(data)
    if errors:
        print(f"{path}: INVALID")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{path}: OK")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Password policy checker and generator")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check a password against the policy")
    c.add_argument("password", nargs="?",
                   help="password (omit to be prompted / read from stdin; avoids shell history)")
    c.add_argument("-p", "--policy", help="path to policy JSON (default: built-in policy)")
    c.add_argument("--json", action="store_true", help="output JSON")
    c.set_defaults(func=cmd_check)

    g = sub.add_parser("generate", help="generate random passwords satisfying the policy")
    g.add_argument("-p", "--policy", help="path to policy JSON (default: built-in policy)")
    g.add_argument("-l", "--length", type=int, help="length (at least policy min_length)")
    g.add_argument("-n", "--count", type=int, default=1, help="number of passwords")
    g.add_argument("--show-entropy", action="store_true", help="print entropy next to each password")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate-policy", help="validate a policy JSON file")
    v.add_argument("policy", nargs="?", help="path to policy file (default: policy.json)")
    v.set_defaults(func=cmd_validate_policy)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
