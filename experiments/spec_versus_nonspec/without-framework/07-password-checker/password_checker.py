#!/usr/bin/env python3
"""Password Policy Checker — WITHOUT framework. Direct implementation."""
import argparse
import json
import math
import os
import random
import string
import sys

POLICY_FILE = "policy.json"

def load_policy():
    if os.path.exists(POLICY_FILE):
        return json.load(open(POLICY_FILE))
    return {
        "min_length": 8, "max_length": 128,
        "require_uppercase": True, "require_lowercase": True,
        "require_digits": True, "require_special": True,
        "special_chars": list(string.punctuation),
        "forbidden_words": [], "min_entropy_bits": 30
    }

def entropy(pw):
    if not pw: return 0
    from collections import Counter
    cnt = Counter(pw)
    n = len(pw)
    return -sum((c/n)*math.log2(c/n) for c in cnt.values()) * n

def check(pw, policy):
    errors = []
    if len(pw) < policy.get("min_length", 0):
        errors.append(f"Too short (min {policy['min_length']})")
    if len(pw) > policy.get("max_length", 9999):
        errors.append(f"Too long (max {policy['max_length']})")
    if policy.get("require_uppercase") and not any(c.isupper() for c in pw):
        errors.append("Missing uppercase")
    if policy.get("require_lowercase") and not any(c.islower() for c in pw):
        errors.append("Missing lowercase")
    if policy.get("require_digits") and not any(c.isdigit() for c in pw):
        errors.append("Missing digit")
    if policy.get("require_special"):
        sc = policy.get("special_chars", list(string.punctuation))
        if not any(c in sc for c in pw):
            errors.append("Missing special char")
    for word in policy.get("forbidden_words", []):
        if word.lower() in pw.lower():
            errors.append(f"Contains forbidden word: {word}")
    min_ent = policy.get("min_entropy_bits", 0)
    e = entropy(pw)
    if e < min_ent:
        errors.append(f"Low entropy: {e:.1f} bits (need {min_ent})")
    return errors

def generate(policy):
    min_l = policy.get("min_length", 8)
    max_l = min(policy.get("max_length", 128), max(min_l + 8, 16))
    sc = policy.get("special_chars", list(string.punctuation))
    pool = string.ascii_letters + string.digits + "".join(sc)
    for _ in range(1000):
        l = random.randint(min_l, max_l)
        chars = []
        if policy.get("require_uppercase"): chars.append(random.choice(string.ascii_uppercase))
        if policy.get("require_lowercase"): chars.append(random.choice(string.ascii_lowercase))
        if policy.get("require_digits"): chars.append(random.choice(string.digits))
        if policy.get("require_special") and sc: chars.append(random.choice(sc))
        while len(chars) < l: chars.append(random.choice(pool))
        random.shuffle(chars)
        pw = "".join(chars)
        if not check(pw, policy):
            return pw
    return None

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
c = sub.add_parser("check"); c.add_argument("password")
sub.add_parser("generate")
sub.add_parser("validate-policy")

args = parser.parse_args()
policy = load_policy()

if args.cmd == "check":
    errs = check(args.password, policy)
    if errs:
        print("FAILED:")
        for e in errs: print(f"  - {e}")
        sys.exit(1)
    else:
        print("PASSED")
elif args.cmd == "generate":
    pw = generate(policy)
    if pw:
        print(f"Generated: {pw}")
    else:
        print("Failed to generate password", file=sys.stderr); sys.exit(1)
elif args.cmd == "validate-policy":
    errs = []
    if policy.get("min_length", 0) > policy.get("max_length", 9999):
        errs.append("min_length > max_length")
    if errs:
        print("Policy invalid:", errs); sys.exit(1)
    else:
        print("Policy valid")
