#!/usr/bin/env python3
"""Secret Vault CLI: TTL-bound secrets encrypted with Fernet (PBKDF2HMAC key).

Master password: environment variable VAULT_MASTER_KEY only.
Exit codes: 0 ok, 1 user error, 2 auth/lockout, 3 expired.
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

MAGIC = b"VLT1"
SALT_LEN = 16
ITERATIONS = 200_000
KEY_RE = re.compile(r"[a-zA-Z0-9_]{1,64}")
MAX_VALUE_BYTES = 4096
DEFAULT_TTL_DAYS = 90
MAX_FAILURES = 3
AUDIT_TAIL = 20


class Exit(Exception):
    def __init__(self, code, message=None):
        super().__init__(code)
        self.code = code
        self.message = message


def vault_dir():
    return os.path.join(os.path.expanduser("~"), ".vault")


def path(name):
    return os.path.join(vault_dir(), name)


def ensure_dir():
    d = vault_dir()
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(d, 0o700)


def write_private(name, data, append=False):
    ensure_dir()
    target = path(name)
    if append:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(target, 0o600)
        return
    tmp = target + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    os.chmod(target, 0o600)


def derive_key(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password))


def now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- validation

def check_key(key):
    if not KEY_RE.fullmatch(key):
        raise Exit(USER_ERROR, "invalid key: use [a-zA-Z0-9_]{1,64}")
    return key.lower()


def check_value(value):
    try:
        raw = value.encode("utf-8")
    except UnicodeEncodeError:
        raise Exit(USER_ERROR, "value is not valid UTF-8")
    if not raw:
        raise Exit(USER_ERROR, "empty value")
    if len(raw) > MAX_VALUE_BYTES:
        raise Exit(USER_ERROR, "value exceeds %d bytes" % MAX_VALUE_BYTES)
    return value


def read_value(arg):
    if arg is None:
        arg = sys.stdin.read()
        if arg.endswith("\n"):
            arg = arg[:-1]
    return check_value(arg)


def check_ttl(ttl):
    if ttl is None:
        return DEFAULT_TTL_DAYS
    if ttl < 1:
        raise Exit(USER_ERROR, "--ttl must be a positive number of days")
    return ttl


# ------------------------------------------------------------------ lockout

def read_failures():
    try:
        with open(path(".failcount")) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def record_failure():
    n = read_failures() + 1
    write_private(".failcount", str(n).encode())
    if n >= MAX_FAILURES:
        write_private(".lockout", b"locked\n")


def clear_failures():
    try:
        os.remove(path(".failcount"))
    except OSError:
        pass


# -------------------------------------------------------------------- vault

class Vault:
    def __init__(self):
        if os.path.exists(path(".lockout")):
            raise Exit(AUTH_ERROR, "vault is locked out")
        password = os.environ.get("VAULT_MASTER_KEY", "")
        if not password:
            raise Exit(AUTH_ERROR, "VAULT_MASTER_KEY is not set")
        self.password = password.encode("utf-8", "surrogateescape")
        self.exists = os.path.exists(path("vault.enc"))
        if not self.exists:
            self.salt = os.urandom(SALT_LEN)
            self.fernet = None
            self.data = {}
            return
        with open(path("vault.enc"), "rb") as f:
            blob = f.read()
        if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + SALT_LEN:
            raise Exit(USER_ERROR, "vault file is corrupt")
        self.salt = blob[len(MAGIC):len(MAGIC) + SALT_LEN]
        self.fernet = Fernet(derive_key(self.password, self.salt))
        try:
            plain = self.fernet.decrypt(blob[len(MAGIC) + SALT_LEN:])
            self.data = json.loads(plain.decode("utf-8"))
        except (InvalidToken, ValueError):
            record_failure()
            raise Exit(AUTH_ERROR, "authentication failed")
        clear_failures()

    def save(self):
        if self.fernet is None:
            self.fernet = Fernet(derive_key(self.password, self.salt))
        token = self.fernet.encrypt(json.dumps(self.data).encode("utf-8"))
        write_private("vault.enc", MAGIC + self.salt + token)


def is_expired(entry):
    try:
        return datetime.fromisoformat(entry["expires"]) <= now()
    except (KeyError, ValueError, TypeError):
        return True


def new_entry(value, ttl):
    return {"value": value, "expires": (now() + timedelta(days=ttl)).isoformat()}


def mask(value):
    k = min(4, len(value) - 1)
    return value[:max(k, 0)] + "***"


# ----------------------------------------------------------------- commands

def cmd_set(args):
    key = check_key(args.key)
    value = read_value(args.value)
    ttl = check_ttl(args.ttl)
    v = Vault()
    v.data[key] = new_entry(value, ttl)
    v.save()
    return key


def cmd_get(args):
    key = check_key(args.key)
    v = Vault()
    entry = v.data.get(key)
    if entry is None:
        raise Exit(USER_ERROR, "no such key")
    if is_expired(entry):
        raise Exit(EXPIRED, "key is expired")
    sys.stdout.write(entry["value"] + "\n")
    return key


def cmd_list(args):
    v = Vault()
    for key in sorted(v.data):
        entry = v.data[key]
        shown = "[expired]" if is_expired(entry) else mask(entry["value"])
        sys.stdout.write("%s\t%s\t%s\n" % (key, shown, entry.get("expires", "")))
    return "-"


def cmd_delete(args):
    key = check_key(args.key)
    v = Vault()
    if key not in v.data:
        raise Exit(USER_ERROR, "no such key")
    del v.data[key]
    v.save()
    return key


def cmd_rotate(args):
    key = check_key(args.key)
    value = read_value(args.value)
    ttl = check_ttl(args.ttl)
    v = Vault()
    if key not in v.data:
        raise Exit(USER_ERROR, "no such key")
    v.data[key] = new_entry(value, ttl)
    v.save()
    return key


def cmd_audit(args):
    ensure_dir()
    try:
        with open(path("audit.log"), "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    for line in lines[-AUDIT_TAIL:]:
        sys.stdout.write(line + "\n")
    return "-"


def audit_log(command, key, code):
    line = "%s %s key=%s exit=%d\n" % (now().isoformat(), command, key, code)
    write_private("audit.log", line.encode("utf-8"), append=True)


# --------------------------------------------------------------------- main

class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Never echo argv: it may contain a secret value.
        sys.stderr.write("usage error (see --help)\n")
        raise SystemExit(USER_ERROR)


def build_parser():
    p = Parser(prog="vault",
               description="Secret vault. Master password: VAULT_MASTER_KEY.")
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)
    for name, fn, has_value in (("set", cmd_set, True), ("rotate", cmd_rotate, True),
                                ("get", cmd_get, False), ("delete", cmd_delete, False)):
        s = sub.add_parser(name)
        s.add_argument("key")
        if has_value:
            s.add_argument("value", nargs="?", default=None,
                           help="omit to read the value from stdin")
            s.add_argument("--ttl", type=int, metavar="DAYS", default=None,
                           help="days until expiry (default 90)")
        s.set_defaults(fn=fn)
    for name, fn in (("list", cmd_list), ("audit", cmd_audit)):
        s = sub.add_parser(name)
        s.set_defaults(fn=fn)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    key = "-"
    code = OK
    try:
        key = args.fn(args) or "-"
    except Exit as e:
        code = e.code
        if e.message:
            sys.stderr.write("error: %s\n" % e.message)
        if hasattr(args, "key") and KEY_RE.fullmatch(args.key):
            key = args.key.lower()
    if args.command != "audit":
        try:
            audit_log(args.command, key, code)
        except OSError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
