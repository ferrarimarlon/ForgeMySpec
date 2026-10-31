#!/usr/bin/env python3
"""Secret Vault CLI.

The master password is read from the VAULT_MASTER_KEY environment variable.
Values for set/rotate are read from the positional argument or, if omitted,
from stdin (preferred, since argv is visible to other local users).

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

EXIT_OK, EXIT_USER, EXIT_AUTH, EXIT_EXPIRED = 0, 1, 2, 3

MAGIC = b"VLT1"
SALT_LEN = 16
ITERATIONS = 200_000
MAX_ATTEMPTS = 3
MAX_VALUE_BYTES = 4096
DEFAULT_TTL_DAYS = 90
KEY_RE = re.compile(r"[a-zA-Z0-9_]{1,64}")

VAULT_DIR = Path.home() / ".vault"
VAULT_FILE = VAULT_DIR / "vault.enc"
AUDIT_LOG = VAULT_DIR / "audit.log"
LOCKOUT_FILE = VAULT_DIR / ".lockout"
ATTEMPTS_FILE = VAULT_DIR / ".attempts"


class VaultExit(Exception):
    def __init__(self, code, msg=None):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def now():
    return datetime.now(timezone.utc)


def ensure_dir():
    VAULT_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(VAULT_DIR, 0o700)


def write_private(path, data, append=False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, data)
    finally:
        os.close(fd)


def audit_log(action, key=None, result="ok"):
    """Record an event. Never receives values."""
    ensure_dir()
    parts = [now().isoformat(timespec="seconds"), action, key or "-", result]
    write_private(AUDIT_LOG, (" ".join(parts) + "\n").encode(), append=True)


def validate_key(key):
    if not KEY_RE.fullmatch(key):
        raise VaultExit(EXIT_USER, "invalid key: must match [a-zA-Z0-9_]{1,64}")
    return key.lower()


def validate_value(value):
    try:
        raw = value.encode("utf-8")
    except UnicodeEncodeError:
        raise VaultExit(EXIT_USER, "value is not valid UTF-8")
    if len(raw) > MAX_VALUE_BYTES:
        raise VaultExit(EXIT_USER, f"value exceeds {MAX_VALUE_BYTES} bytes")
    return value


def read_value(arg):
    if arg is not None:
        return validate_value(arg)
    try:
        data = sys.stdin.buffer.read(MAX_VALUE_BYTES + 3)
        value = data.decode("utf-8")
    except UnicodeDecodeError:
        raise VaultExit(EXIT_USER, "value is not valid UTF-8")
    if value.endswith("\n"):
        value = value[:-1]
    if not value:
        raise VaultExit(EXIT_USER, "empty value")
    return validate_value(value)


def get_password():
    pw = os.environ.get("VAULT_MASTER_KEY")
    if not pw:
        raise VaultExit(EXIT_USER, "VAULT_MASTER_KEY environment variable is not set")
    return pw.encode("utf-8")


def derive_fernet(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password)))


def check_lockout():
    if LOCKOUT_FILE.exists():
        raise VaultExit(EXIT_AUTH, "vault is locked out; remove ~/.vault/.lockout to unlock")


def register_failure():
    try:
        count = int(ATTEMPTS_FILE.read_text().strip())
    except (OSError, ValueError):
        count = 0
    count += 1
    if count >= MAX_ATTEMPTS:
        write_private(LOCKOUT_FILE, now().isoformat().encode())
        ATTEMPTS_FILE.unlink(missing_ok=True)
        audit_log("auth", result="lockout")
        raise VaultExit(EXIT_AUTH, "too many failed attempts; vault locked")
    write_private(ATTEMPTS_FILE, str(count).encode())
    audit_log("auth", result="failed")
    raise VaultExit(EXIT_AUTH, "wrong master password")


def load(password):
    """Return (fernet, salt, data dict). Creates fresh state if no vault exists."""
    ensure_dir()
    check_lockout()
    if not VAULT_FILE.exists():
        salt = os.urandom(SALT_LEN)
        return derive_fernet(password, salt), salt, {}
    blob = VAULT_FILE.read_bytes()
    if len(blob) < len(MAGIC) + SALT_LEN or not blob.startswith(MAGIC):
        raise VaultExit(EXIT_USER, "vault file is corrupt")
    salt = blob[len(MAGIC):len(MAGIC) + SALT_LEN]
    token = blob[len(MAGIC) + SALT_LEN:]
    f = derive_fernet(password, salt)
    try:
        data = json.loads(f.decrypt(token))
    except InvalidToken:
        register_failure()
    except ValueError:
        raise VaultExit(EXIT_USER, "vault file is corrupt")
    ATTEMPTS_FILE.unlink(missing_ok=True)
    return f, salt, data


def save(f, salt, data):
    token = f.encrypt(json.dumps(data).encode("utf-8"))
    tmp = VAULT_DIR / "vault.enc.tmp"
    write_private(tmp, MAGIC + salt + token)
    os.replace(tmp, VAULT_FILE)
    os.chmod(VAULT_FILE, 0o600)


def is_expired(entry):
    return datetime.fromisoformat(entry["expires"]) <= now()


def make_entry(value, ttl):
    return {"value": value, "expires": (now() + timedelta(days=ttl)).isoformat()}


def cmd_set(args):
    key = validate_key(args.key)
    value = read_value(args.value)
    f, salt, data = load(get_password())
    data[key] = make_entry(value, args.ttl)
    save(f, salt, data)
    audit_log("set", key)


def cmd_get(args):
    key = validate_key(args.key)
    f, salt, data = load(get_password())
    entry = data.get(key)
    if entry is None:
        audit_log("get", key, "missing")
        raise VaultExit(EXIT_USER, f"no such key: {key}")
    if is_expired(entry):
        audit_log("get", key, "expired")
        raise VaultExit(EXIT_EXPIRED, f"key expired: {key}")
    audit_log("get", key)
    sys.stdout.write(entry["value"])
    sys.stdout.flush()


def cmd_list(args):
    f, salt, data = load(get_password())
    for key in sorted(data):
        entry = data[key]
        if is_expired(entry):
            shown = "[EXPIRED]"
        else:
            value = entry["value"]
            # Never reveal a whole short value: only show a prefix if more remains.
            shown = (value[:4] if len(value) > 4 else "") + "***"
        print(f"{key}\t{shown}\texpires={entry['expires']}")
    audit_log("list")


def cmd_delete(args):
    key = validate_key(args.key)
    f, salt, data = load(get_password())
    if key not in data:
        audit_log("delete", key, "missing")
        raise VaultExit(EXIT_USER, f"no such key: {key}")
    del data[key]
    save(f, salt, data)
    audit_log("delete", key)


def cmd_rotate(args):
    key = validate_key(args.key)
    f, salt, data = load(get_password())
    if key not in data:
        audit_log("rotate", key, "missing")
        raise VaultExit(EXIT_USER, f"no such key: {key}")
    value = read_value(args.value)
    data[key] = make_entry(value, args.ttl)
    save(f, salt, data)
    audit_log("rotate", key)


def cmd_audit(args):
    load(get_password())  # authenticate; the log reveals key names
    audit_log("audit")
    lines = AUDIT_LOG.read_text().splitlines()[-20:]
    for line in lines:
        print(line)


def positive_int(s):
    n = int(s)
    if n < 1:
        raise argparse.ArgumentTypeError("must be a positive number of days")
    return n


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise VaultExit(EXIT_USER, message)


def build_parser():
    p = Parser(prog="vault.py", description="Secret vault (master password in $VAULT_MASTER_KEY)")
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)

    s = sub.add_parser("set", help="store a secret (value from stdin if omitted)")
    s.add_argument("key")
    s.add_argument("value", nargs="?")
    s.add_argument("--ttl", type=positive_int, default=DEFAULT_TTL_DAYS, metavar="DAYS")
    s.set_defaults(func=cmd_set)

    s = sub.add_parser("get", help="print a secret's value")
    s.add_argument("key")
    s.set_defaults(func=cmd_get)

    s = sub.add_parser("list", help="list keys with masked values")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("delete", help="delete a secret")
    s.add_argument("key")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("rotate", help="replace an existing secret's value and reset its TTL")
    s.add_argument("key")
    s.add_argument("value", nargs="?")
    s.add_argument("--ttl", type=positive_int, default=DEFAULT_TTL_DAYS, metavar="DAYS")
    s.set_defaults(func=cmd_rotate)

    s = sub.add_parser("audit", help="show the last 20 audit log lines")
    s.set_defaults(func=cmd_audit)
    return p


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        args.func(args)
    except VaultExit as e:
        if e.msg:
            print(f"error: {e.msg}", file=sys.stderr)
        return e.code
    except OSError as e:
        print(f"error: {e.strerror or 'I/O error'}", file=sys.stderr)
        return EXIT_USER
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
