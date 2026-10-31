#!/usr/bin/env python3
"""Secret Vault CLI: Fernet-encrypted key/value store with TTL, lockout and audit log.

Exit codes: 0 ok, 1 user error, 2 auth/lockout, 3 expired.
The master password is read only from the VAULT_MASTER_KEY environment variable.
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

ENV_VAR = "VAULT_MASTER_KEY"
SALT_LEN = 16
ITERATIONS = 200_000
KEY_RE = re.compile(r"[a-zA-Z0-9_]{1,64}")
MAX_VALUE_BYTES = 4096
DEFAULT_TTL_DAYS = 90
MAX_ATTEMPTS = 3
AUDIT_TAIL = 20

OK, USER_ERROR, AUTH_ERROR, EXPIRED = 0, 1, 2, 3


class VaultExit(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code = code
        self.message = message


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse default exits 2 and may echo input
        raise VaultExit(USER_ERROR, "usage error")

    def exit(self, status=0, message=None):
        if status == 0:
            raise VaultExit(OK)
        raise VaultExit(USER_ERROR, "usage error")


def vault_dir():
    return Path.home() / ".vault"


def paths():
    d = vault_dir()
    return d, d / "vault.enc", d / "audit.log", d / ".lockout", d / ".attempts"


def ensure_dir():
    d = vault_dir()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def now():
    return datetime.now(timezone.utc)


def derive_key(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password))


def audit_log(command, key, outcome):
    """Append one line; only command, key name and outcome, never values."""
    ensure_dir()
    _, _, log, _, _ = paths()
    line = "%s %s %s %s\n" % (now().isoformat(), command, key or "-", outcome)
    fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(log, 0o600)


def write_private(path, data):
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def register_failure(command):
    ensure_dir()
    _, _, _, lockout, attempts = paths()
    try:
        count = int(attempts.read_text().strip())
    except (OSError, ValueError):
        count = 0
    count += 1
    write_private(attempts, str(count).encode())
    if count >= MAX_ATTEMPTS:
        write_private(lockout, b"locked\n")
        audit_log(command, None, "lockout")
    else:
        audit_log(command, None, "auth-failed")


def load_vault(command, password):
    """Return the entries dict; exits 2 on a wrong password."""
    _, enc, _, _, attempts = paths()
    if not enc.exists():
        return {}
    blob = enc.read_bytes()
    if len(blob) <= SALT_LEN:
        raise VaultExit(USER_ERROR, "vault file is corrupt")
    salt, token = blob[:SALT_LEN], blob[SALT_LEN:]
    try:
        plain = Fernet(derive_key(password, salt)).decrypt(token)
    except InvalidToken:
        register_failure(command)
        _, _, _, lockout, _ = paths()
        if lockout.exists():
            raise VaultExit(AUTH_ERROR, "too many failed attempts: vault locked")
        raise VaultExit(AUTH_ERROR, "authentication failed")
    try:
        attempts.unlink()
    except FileNotFoundError:
        pass
    try:
        return json.loads(plain.decode("utf-8"))
    except ValueError:
        raise VaultExit(USER_ERROR, "vault file is corrupt")


def save_vault(password, entries):
    ensure_dir()
    _, enc, _, _, _ = paths()
    salt = os.urandom(SALT_LEN)
    token = Fernet(derive_key(password, salt)).encrypt(json.dumps(entries).encode("utf-8"))
    write_private(enc, salt + token)


def check_key(raw):
    if not KEY_RE.fullmatch(raw):
        raise VaultExit(USER_ERROR, "invalid key: use [a-zA-Z0-9_]{1,64}")
    return raw.lower()


def check_value(value):
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise VaultExit(USER_ERROR, "value is not valid UTF-8")
    if size > MAX_VALUE_BYTES:
        raise VaultExit(USER_ERROR, "value exceeds 4096 bytes")


def check_ttl(ttl):
    if ttl < 0:
        raise VaultExit(USER_ERROR, "ttl must be a non-negative number of days")
    return ttl


def is_expired(entry):
    try:
        return datetime.fromisoformat(entry["expires"]) <= now()
    except (KeyError, ValueError, TypeError):
        return True


def build_parser():
    p = _Parser(prog="vault.py", description="Secret vault; password from VAULT_MASTER_KEY.")
    sub = p.add_subparsers(dest="command", required=True, parser_class=_Parser)
    s = sub.add_parser("set")
    s.add_argument("key")
    s.add_argument("value")
    s.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS)
    g = sub.add_parser("get")
    g.add_argument("key")
    sub.add_parser("list")
    d = sub.add_parser("delete")
    d.add_argument("key")
    r = sub.add_parser("rotate")
    r.add_argument("key")
    r.add_argument("value")
    r.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS)
    sub.add_parser("audit")
    return p


def run(argv, out):
    args = build_parser().parse_args(argv)
    cmd = args.command

    key = None
    if cmd in ("set", "get", "delete", "rotate"):
        key = check_key(args.key)
    if cmd in ("set", "rotate"):
        check_value(args.value)
        check_ttl(args.ttl)

    _, _, _, lockout, _ = paths()
    if lockout.exists():
        raise VaultExit(AUTH_ERROR, "vault is locked")
    password = os.environ.get(ENV_VAR, "")
    if not password:
        raise VaultExit(AUTH_ERROR, "%s is not set" % ENV_VAR)
    password = password.encode("utf-8")

    entries = load_vault(cmd, password)

    if cmd in ("set", "rotate"):
        if cmd == "rotate" and key not in entries:
            audit_log(cmd, key, "missing")
            raise VaultExit(USER_ERROR, "key not found")
        expires = (now() + timedelta(days=args.ttl)).isoformat()
        entries[key] = {"value": args.value, "expires": expires}
        save_vault(password, entries)
        audit_log(cmd, key, "ok")
    elif cmd == "get":
        entry = entries.get(key)
        if entry is None:
            audit_log(cmd, key, "missing")
            raise VaultExit(USER_ERROR, "key not found")
        if is_expired(entry):
            audit_log(cmd, key, "expired")
            raise VaultExit(EXPIRED, "key expired")
        audit_log(cmd, key, "ok")
        out.write(entry["value"] + "\n")
    elif cmd == "list":
        for k in sorted(entries):
            if is_expired(entries[k]):
                out.write("%s  expired\n" % k)
            else:
                out.write("%s  %s***\n" % (k, entries[k]["value"][:4]))
        audit_log(cmd, None, "ok")
    elif cmd == "delete":
        if key not in entries:
            audit_log(cmd, key, "missing")
            raise VaultExit(USER_ERROR, "key not found")
        del entries[key]
        save_vault(password, entries)
        audit_log(cmd, key, "ok")
    elif cmd == "audit":
        audit_log(cmd, None, "ok")
        _, _, log, _, _ = paths()
        lines = log.read_text(encoding="utf-8").splitlines()
        for line in lines[-AUDIT_TAIL:]:
            out.write(line + "\n")
    return OK


def main(argv=None):
    try:
        return run(sys.argv[1:] if argv is None else argv, sys.stdout)
    except VaultExit as e:
        if e.message:
            print(e.message, file=sys.stderr)
        return e.code
    except Exception:
        print("internal error", file=sys.stderr)
        return USER_ERROR


if __name__ == "__main__":
    sys.exit(main())
