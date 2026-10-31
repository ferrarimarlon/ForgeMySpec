#!/usr/bin/env python3
"""Secret Vault CLI: Fernet-encrypted key/value store with TTL, audit log and lockout.

Exit codes: 0 ok, 1 user error, 2 auth/lockout, 3 expired.
The master password comes only from the VAULT_MASTER_KEY environment variable.
"""
import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

OK, USER_ERROR, AUTH_ERROR, EXPIRED = 0, 1, 2, 3

SALT_LEN = 16
KDF_ITERATIONS = 200000
MAX_VALUE_BYTES = 4096
DEFAULT_TTL_DAYS = 90
MAX_ATTEMPTS = 3
AUDIT_TAIL = 20
KEY_RE = re.compile(r"[a-zA-Z0-9_]{1,64}")


class Exit(Exception):
    def __init__(self, code, message=None):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on bad usage; the vault reserves 2 for auth, so use 1."""

    def error(self, message):
        # Do not echo the message: it could contain argv text (possibly a value).
        sys.stderr.write("vault: invalid usage (see --help)\n")
        raise SystemExit(USER_ERROR)


def vault_dir():
    return os.path.join(os.path.expanduser("~"), ".vault")


def paths():
    d = vault_dir()
    return {
        "dir": d,
        "vault": os.path.join(d, "vault.enc"),
        "audit": os.path.join(d, "audit.log"),
        "lockout": os.path.join(d, ".lockout"),
        "attempts": os.path.join(d, ".attempts"),
    }


def ensure_dir(p):
    os.makedirs(p["dir"], mode=0o700, exist_ok=True)
    os.chmod(p["dir"], 0o700)


def write_private(path, data):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def derive_fernet(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=KDF_ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8"))))


def now():
    return datetime.now(timezone.utc)


def audit_log(p, command, key, status):
    """Append timestamp, command, key name and status. Never a value."""
    ensure_dir(p)
    line = "%s\t%s\t%s\t%s\n" % (now().isoformat(), command, key or "-", status)
    fd = os.open(p["audit"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(line)
    os.chmod(p["audit"], 0o600)


def validate_key(key):
    if not KEY_RE.fullmatch(key):
        raise Exit(USER_ERROR, "invalid key: must match [a-zA-Z0-9_]{1,64}")
    return key.lower()


def validate_value(value):
    try:
        raw = value.encode("utf-8")
    except UnicodeEncodeError:
        raise Exit(USER_ERROR, "value is not valid UTF-8")
    if len(raw) > MAX_VALUE_BYTES:
        raise Exit(USER_ERROR, "value exceeds %d bytes" % MAX_VALUE_BYTES)
    return value


def get_password():
    password = os.environ.get("VAULT_MASTER_KEY", "")
    if not password:
        raise Exit(USER_ERROR, "VAULT_MASTER_KEY is not set")
    return password


def read_attempts(p):
    try:
        with open(p["attempts"], "r") as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def register_failure(p):
    ensure_dir(p)
    n = read_attempts(p) + 1
    if n >= MAX_ATTEMPTS:
        write_private(p["lockout"], b"locked\n")
        try:
            os.remove(p["attempts"])
        except OSError:
            pass
    else:
        write_private(p["attempts"], str(n).encode())


def clear_failures(p):
    try:
        os.remove(p["attempts"])
    except OSError:
        pass


def load(p, password):
    """Return (salt, data). A missing vault yields a fresh salt and empty data."""
    if not os.path.exists(p["vault"]):
        return os.urandom(SALT_LEN), {}
    with open(p["vault"], "rb") as f:
        blob = f.read()
    if len(blob) <= SALT_LEN:
        raise Exit(USER_ERROR, "vault file is corrupt")
    salt, token = blob[:SALT_LEN], blob[SALT_LEN:]
    try:
        data = json.loads(derive_fernet(password, salt).decrypt(token))
    except InvalidToken:
        register_failure(p)
        raise Exit(AUTH_ERROR, "authentication failed")
    except ValueError:
        raise Exit(USER_ERROR, "vault file is corrupt")
    clear_failures(p)
    return salt, data


def save(p, password, salt, data):
    ensure_dir(p)
    token = derive_fernet(password, salt).encrypt(json.dumps(data).encode("utf-8"))
    write_private(p["vault"], salt + token)


def expiry_for(days):
    return (now() + timedelta(days=days)).isoformat()


def is_expired(entry):
    return datetime.fromisoformat(entry["expires"]) <= now()


def mask(value):
    # value[:4] + ***, but never reveal a whole short value.
    shown = value[:4] if len(value) > 4 else value[:max(len(value) - 1, 0)]
    return shown + "***"


def read_value(args):
    if args.value is None:
        return sys.stdin.read().rstrip("\n")
    return args.value


def run(args, p):
    cmd = args.command
    key = None
    value = None
    if cmd in ("set", "get", "delete", "rotate"):
        key = validate_key(args.key)
    if cmd in ("set", "rotate"):
        value = validate_value(read_value(args))
        if args.ttl < 0:
            raise Exit(USER_ERROR, "--ttl must be >= 0")

    password = get_password()
    if os.path.exists(p["lockout"]):
        raise Exit(AUTH_ERROR, "vault is locked out")

    salt, data = load(p, password)

    if cmd == "set":
        data[key] = {"value": value, "expires": expiry_for(args.ttl)}
        save(p, password, salt, data)
        audit_log(p, cmd, key, "ok")
    elif cmd == "get":
        if key not in data:
            raise Exit(USER_ERROR, "no such key")
        if is_expired(data[key]):
            audit_log(p, cmd, key, "expired")
            raise Exit(EXPIRED, "key is expired")
        audit_log(p, cmd, key, "ok")
        sys.stdout.write(data[key]["value"] + "\n")
    elif cmd == "list":
        audit_log(p, cmd, None, "ok")
        for k in sorted(data):
            sys.stdout.write("%s\t%s\t%s\n" % (k, mask(data[k]["value"]), data[k]["expires"]))
    elif cmd == "delete":
        if key not in data:
            raise Exit(USER_ERROR, "no such key")
        del data[key]
        save(p, password, salt, data)
        audit_log(p, cmd, key, "ok")
    elif cmd == "rotate":
        if key not in data:
            raise Exit(USER_ERROR, "no such key")
        data[key] = {"value": value, "expires": expiry_for(args.ttl)}
        save(p, password, salt, data)
        audit_log(p, cmd, key, "ok")
    elif cmd == "audit":
        audit_log(p, cmd, None, "ok")
        with open(p["audit"], "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        for line in lines[-AUDIT_TAIL:]:
            sys.stdout.write(line + "\n")
    return OK


def build_parser():
    ap = Parser(prog="vault.py", description="Secret vault (password in VAULT_MASTER_KEY)")
    sub = ap.add_subparsers(dest="command", required=True, parser_class=Parser)
    for name in ("set", "rotate"):
        sp = sub.add_parser(name)
        sp.add_argument("key")
        sp.add_argument("value", nargs="?", help="omit to read the value from stdin")
        sp.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, metavar="DAYS")
    for name in ("get", "delete"):
        sub.add_parser(name).add_argument("key")
    sub.add_parser("list")
    sub.add_parser("audit")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    p = paths()
    try:
        return run(args, p)
    except Exit as e:
        if e.message:
            sys.stderr.write("vault: %s\n" % e.message)
        # Best-effort audit of failures; key names and status only.
        try:
            if e.code != EXPIRED:
                audit_log(p, args.command, getattr(args, "key", None),
                          "error:%d" % e.code)
        except OSError:
            pass
        return e.code


if __name__ == "__main__":
    sys.exit(main())
