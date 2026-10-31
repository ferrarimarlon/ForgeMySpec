#!/usr/bin/env python3
"""Secret Vault CLI.

Usage:
  VAULT_MASTER_KEY=... vault.py set KEY [VALUE] [--ttl DAYS]
  VAULT_MASTER_KEY=... vault.py get KEY
  VAULT_MASTER_KEY=... vault.py list
  VAULT_MASTER_KEY=... vault.py delete KEY
  VAULT_MASTER_KEY=... vault.py rotate KEY [VALUE] [--ttl DAYS]
  vault.py audit

If VALUE is omitted for set/rotate it is read from stdin (keeps it out of argv).

Exit codes: 0 ok, 1 user error, 2 auth/lockout, 3 expired.
"""
import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

OK, USER_ERROR, AUTH_ERROR, EXPIRED = 0, 1, 2, 3

VAULT_DIR = Path.home() / ".vault"
VAULT_FILE = VAULT_DIR / "vault.enc"
AUDIT_LOG = VAULT_DIR / "audit.log"
LOCKOUT_FILE = VAULT_DIR / ".lockout"
ATTEMPTS_FILE = VAULT_DIR / ".attempts"

MAGIC = b"VLT1"
SALT_LEN = 16
ITERATIONS = 200_000
MAX_ATTEMPTS = 3
MAX_VALUE_BYTES = 4096
DEFAULT_TTL_DAYS = 90
KEY_RE = re.compile(r"[a-zA-Z0-9_]{1,64}", re.ASCII)


class VaultExit(Exception):
    def __init__(self, code, msg=None):
        super().__init__(msg)
        self.code = code
        self.msg = msg


class QuietParser(argparse.ArgumentParser):
    """argparse errors can echo argv (and thus secret values); keep them generic."""

    def error(self, message):
        sys.stderr.write("error: invalid arguments (see --help)\n")
        raise SystemExit(USER_ERROR)


# ---------- filesystem helpers ----------

def ensure_dir():
    VAULT_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(VAULT_DIR, 0o700)


def write_private(path, data, append=False):
    """Write bytes to path with mode 600 (atomic replace unless appending)."""
    if append:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "ab") as f:
            f.write(data)
        os.chmod(path, 0o600)
        return
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def now():
    return datetime.now(timezone.utc)


def audit_log(action, key=None, result="ok"):
    """Record an event. Never receives values."""
    ensure_dir()
    parts = [now().isoformat(timespec="seconds"), action, key or "-", result]
    write_private(AUDIT_LOG, (" ".join(parts) + "\n").encode(), append=True)


# ---------- crypto ----------

def master_password():
    pw = os.environ.get("VAULT_MASTER_KEY")
    if not pw:
        raise VaultExit(USER_ERROR, "VAULT_MASTER_KEY environment variable is not set")
    return pw.encode("utf-8")


def derive_fernet(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password)))


def save(password, data):
    salt = os.urandom(SALT_LEN)
    token = derive_fernet(password, salt).encrypt(json.dumps(data).encode("utf-8"))
    ensure_dir()
    write_private(VAULT_FILE, MAGIC + salt + token)


def read_attempts():
    try:
        return int(ATTEMPTS_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0


def register_failure(action):
    attempts = read_attempts() + 1
    write_private(ATTEMPTS_FILE, str(attempts).encode())
    if attempts >= MAX_ATTEMPTS:
        write_private(LOCKOUT_FILE, now().isoformat().encode())
        audit_log(action, result="lockout")
        raise VaultExit(AUTH_ERROR, "too many failed attempts; vault is locked")
    audit_log(action, result="auth_failed")
    raise VaultExit(AUTH_ERROR, "authentication failed")


def check_lockout(action):
    if LOCKOUT_FILE.exists():
        audit_log(action, result="locked_out")
        raise VaultExit(AUTH_ERROR, "vault is locked; remove %s after review to unlock" % LOCKOUT_FILE)


def load(password, action, must_exist=True):
    """Return decrypted dict. Handles lockout accounting."""
    ensure_dir()
    check_lockout(action)
    if not VAULT_FILE.exists():
        if must_exist:
            raise VaultExit(USER_ERROR, "vault does not exist; use 'set' to create it")
        return {}
    blob = VAULT_FILE.read_bytes()
    if len(blob) < len(MAGIC) + SALT_LEN or blob[: len(MAGIC)] != MAGIC:
        raise VaultExit(USER_ERROR, "vault file is corrupt or has an unknown format")
    salt = blob[len(MAGIC): len(MAGIC) + SALT_LEN]
    token = blob[len(MAGIC) + SALT_LEN:]
    try:
        plain = derive_fernet(password, salt).decrypt(token)
    except InvalidToken:
        register_failure(action)
    if ATTEMPTS_FILE.exists():
        ATTEMPTS_FILE.unlink()
    return json.loads(plain)


# ---------- validation ----------

def norm_key(key):
    if not KEY_RE.fullmatch(key):
        raise VaultExit(USER_ERROR, "invalid key: must match [a-zA-Z0-9_]{1,64}")
    return key.lower()


def get_value(arg):
    value = arg if arg is not None else sys.stdin.read().rstrip("\n")
    try:
        raw = value.encode("utf-8")
    except UnicodeEncodeError:
        raise VaultExit(USER_ERROR, "value is not valid UTF-8")
    if len(raw) > MAX_VALUE_BYTES:
        raise VaultExit(USER_ERROR, "value exceeds %d bytes" % MAX_VALUE_BYTES)
    return value


def expiry(ttl):
    if ttl < 1:
        raise VaultExit(USER_ERROR, "--ttl must be at least 1 day")
    try:
        return (now() + timedelta(days=ttl)).isoformat(timespec="seconds")
    except OverflowError:
        raise VaultExit(USER_ERROR, "--ttl is too large")


def is_expired(entry):
    return datetime.fromisoformat(entry["expires"]) <= now()


def mask(value):
    # Never reveal the whole value, even if it is 4 characters or shorter.
    return value[: min(4, max(len(value) - 1, 0))] + "***"


# ---------- commands ----------

def cmd_set(args):
    key, value = norm_key(args.key), get_value(args.value)
    exp = expiry(args.ttl)
    pw = master_password()
    data = load(pw, "set", must_exist=False)
    data[key] = {"value": value, "expires": exp}
    save(pw, data)
    audit_log("set", key)
    return OK


def cmd_get(args):
    key = norm_key(args.key)
    data = load(master_password(), "get")
    entry = data.get(key)
    if entry is None:
        audit_log("get", key, "not_found")
        raise VaultExit(USER_ERROR, "key not found")
    if is_expired(entry):
        audit_log("get", key, "expired")
        raise VaultExit(EXPIRED, "key has expired")
    audit_log("get", key)
    sys.stdout.write(entry["value"] + "\n")
    return OK


def cmd_list(args):
    data = load(master_password(), "list")
    for key in sorted(data):
        entry = data[key]
        if is_expired(entry):
            print("%s\t***\texpires=%s\tEXPIRED" % (key, entry["expires"]))
        else:
            print("%s\t%s\texpires=%s" % (key, mask(entry["value"]), entry["expires"]))
    audit_log("list")
    return OK


def cmd_delete(args):
    key = norm_key(args.key)
    pw = master_password()
    data = load(pw, "delete")
    if key not in data:
        audit_log("delete", key, "not_found")
        raise VaultExit(USER_ERROR, "key not found")
    del data[key]
    save(pw, data)
    audit_log("delete", key)
    return OK


def cmd_rotate(args):
    key, value = norm_key(args.key), get_value(args.value)
    exp = expiry(args.ttl)
    pw = master_password()
    data = load(pw, "rotate")
    if key not in data:
        audit_log("rotate", key, "not_found")
        raise VaultExit(USER_ERROR, "key not found")
    data[key] = {"value": value, "expires": exp}
    save(pw, data)
    audit_log("rotate", key)
    return OK


def cmd_audit(args):
    ensure_dir()
    audit_log("audit")
    lines = AUDIT_LOG.read_text().splitlines()[-20:]
    for line in lines:
        print(line)
    return OK


def build_parser():
    p = QuietParser(prog="vault.py", description="Secret vault (master password in VAULT_MASTER_KEY)")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=QuietParser)
    for name, fn in (("set", cmd_set), ("rotate", cmd_rotate)):
        s = sub.add_parser(name)
        s.add_argument("key")
        s.add_argument("value", nargs="?", help="omit to read from stdin")
        s.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, help="days until expiry (default 90)")
        s.set_defaults(fn=fn)
    for name, fn in (("get", cmd_get), ("delete", cmd_delete)):
        s = sub.add_parser(name)
        s.add_argument("key")
        s.set_defaults(fn=fn)
    for name, fn in (("list", cmd_list), ("audit", cmd_audit)):
        sub.add_parser(name).set_defaults(fn=fn)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except VaultExit as e:
        if e.msg:
            sys.stderr.write("error: %s\n" % e.msg)
        return e.code
    except (OSError, ValueError, KeyError):
        sys.stderr.write("error: vault operation failed\n")
        return USER_ERROR


if __name__ == "__main__":
    sys.exit(main())
