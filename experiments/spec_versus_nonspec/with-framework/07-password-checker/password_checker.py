#!/usr/bin/env python3
"""Password Policy Checker CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: all checks independent, Shannon entropy, generate with retry.
"""
import argparse
import json
import math
import os
import random
import re
import string
import sys
from typing import List


DEFAULT_POLICY = {
    "min_length": 8,
    "max_length": 128,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_special": True,
    "special_chars": list(string.punctuation),
    "forbidden_words": [],
    "min_entropy_bits": 30.0,
}

POLICY_FILE = "policy.json"


def load_policy(path: str) -> dict:
    if not os.path.exists(path):
        return dict(DEFAULT_POLICY)
    with open(path) as f:
        policy = json.load(f)
    merged = dict(DEFAULT_POLICY)
    merged.update(policy)
    return merged


def shannon_entropy(password: str) -> float:
    """Shannon entropy in bits. H = -sum(p * log2(p)) * length gives total bits."""
    if not password:
        return 0.0
    freq = {}
    for ch in password:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(password)
    h_per_char = 0.0
    for count in freq.values():
        p = count / n
        h_per_char -= p * math.log2(p)
    # Total entropy in bits = entropy per character * length
    return h_per_char * n


def check_password(password: str, policy: dict) -> List[str]:
    """Check all rules independently. Returns list of violation messages."""
    violations = []
    # Length
    if len(password) < policy.get("min_length", 0):
        violations.append(f"Too short: minimum {policy['min_length']} characters (got {len(password)})")
    if len(password) > policy.get("max_length", 9999):
        violations.append(f"Too long: maximum {policy['max_length']} characters (got {len(password)})")
    # Character classes
    if policy.get("require_uppercase") and not any(c.isupper() for c in password):
        violations.append("Missing uppercase letter")
    if policy.get("require_lowercase") and not any(c.islower() for c in password):
        violations.append("Missing lowercase letter")
    if policy.get("require_digits") and not any(c.isdigit() for c in password):
        violations.append("Missing digit")
    if policy.get("require_special"):
        special_chars = policy.get("special_chars", list(string.punctuation))
        if not any(c in special_chars for c in password):
            violations.append(f"Missing special character (required: {' '.join(special_chars[:5])}...)")
    # Forbidden words
    pw_lower = password.lower()
    for word in policy.get("forbidden_words", []):
        if word.lower() in pw_lower:
            violations.append(f"Contains forbidden word: '{word}'")
    # Entropy
    min_entropy = policy.get("min_entropy_bits", 0.0)
    if min_entropy > 0:
        ent = shannon_entropy(password)
        if ent < min_entropy:
            violations.append(f"Insufficient entropy: {ent:.2f} bits (minimum {min_entropy})")
    return violations


def generate_password(policy: dict, max_attempts: int = 1000) -> str:
    """Generate a random password that passes all policy rules."""
    min_len = max(policy.get("min_length", 8), 12)
    max_len = min(policy.get("max_length", 128), max(min_len + 8, 20))
    special_chars = policy.get("special_chars", list(string.punctuation))

    for _ in range(max_attempts):
        length = random.randint(min_len, max_len)
        chars = []
        if policy.get("require_uppercase"):
            chars.append(random.choice(string.ascii_uppercase))
        if policy.get("require_lowercase"):
            chars.append(random.choice(string.ascii_lowercase))
        if policy.get("require_digits"):
            chars.append(random.choice(string.digits))
        if policy.get("require_special") and special_chars:
            chars.append(random.choice(special_chars))
        pool = string.ascii_letters + string.digits
        if special_chars:
            pool += "".join(special_chars)
        while len(chars) < length:
            chars.append(random.choice(pool))
        random.shuffle(chars)
        candidate = "".join(chars)
        violations = check_password(candidate, policy)
        if not violations:
            return candidate
    raise RuntimeError("Could not generate compliant password after maximum attempts")


def validate_policy_file(policy: dict) -> List[str]:
    """Validate the policy file itself."""
    errors = []
    min_len = policy.get("min_length")
    max_len = policy.get("max_length")
    if min_len is not None and not isinstance(min_len, int):
        errors.append("min_length must be an integer")
    if max_len is not None and not isinstance(max_len, int):
        errors.append("max_length must be an integer")
    if isinstance(min_len, int) and isinstance(max_len, int) and min_len > max_len:
        errors.append(f"min_length ({min_len}) cannot exceed max_length ({max_len})")
    min_ent = policy.get("min_entropy_bits")
    if min_ent is not None and not isinstance(min_ent, (int, float)):
        errors.append("min_entropy_bits must be a number")
    if isinstance(min_ent, (int, float)) and min_ent < 0:
        errors.append("min_entropy_bits cannot be negative")
    fw = policy.get("forbidden_words")
    if fw is not None and not isinstance(fw, list):
        errors.append("forbidden_words must be a list")
    sc = policy.get("special_chars")
    if sc is not None and not isinstance(sc, list):
        errors.append("special_chars must be a list")
    return errors


def cmd_check(args: argparse.Namespace) -> None:
    policy = load_policy(args.policy)
    password = args.password
    violations = check_password(password, policy)
    if violations:
        print(f"Password FAILED ({len(violations)} violation(s)):")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("Password PASSED all policy checks.")


def cmd_generate(args: argparse.Namespace) -> None:
    policy = load_policy(args.policy)
    try:
        pw = generate_password(policy)
        print(f"Generated password: {pw}")
        violations = check_password(pw, policy)
        if violations:
            print("WARNING: Generated password has violations:", violations)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_validate_policy(args: argparse.Namespace) -> None:
    if not os.path.exists(args.policy):
        print(f"Policy file not found: {args.policy}", file=sys.stderr)
        sys.exit(1)
    with open(args.policy) as f:
        try:
            policy = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    errors = validate_policy_file(policy)
    if errors:
        print(f"Policy INVALID ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("Policy file is valid.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Password Policy Checker CLI")
    parser.add_argument("--policy", default=POLICY_FILE, help="Policy file path")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="Check a password against policy")
    p_check.add_argument("password", help="Password to check")

    sub.add_parser("generate", help="Generate a compliant password")
    sub.add_parser("validate-policy", help="Validate the policy file")

    args = parser.parse_args()
    if args.command == "check":
        cmd_check(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "validate-policy":
        cmd_validate_policy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
