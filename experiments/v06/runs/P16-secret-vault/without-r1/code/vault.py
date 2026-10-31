#!/usr/bin/env python3
"""Secret vault CLI.

The master password is read from the VAULT_MASTER_KEY environment variable.

Exit codes: 0 ok, 1 user error, 2 auth/lockout, 3 expired.
"""
import argparse
import base64
import fcntl
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

KEY_RE = re.compile(r"[a-zA-Z0-9_]{1,64}")
MAX_VALUE_BYTES = 4096
DEFAULT_TTL_DAYS = 90
MAX_TTL_DAYS = 36500
MAX_ATTEMPTS = 3
AUDIT_TAIL = 20
ITERATIONS = 200_000
SALT_LEN = 16
MAGIC = b"VLT1"

VAULT_DIR = Path.home() / ".vault"
VAULT_FILE = VAULT_DIR / "vault.enc"
AUDIT_FILE = VAULT_DIR / "audit.log"
LOCKOUT_FILE = VAULT_DIR / ".lockout"
ATTEMPTS_FILE = VAULT_DIR / ".attempts"
LOCK_FILE = VAULT_DIR / ".lock"


class VaultExit(Exception):
    def __init__(self, code, message=None):
        super().__init__(message)
        self.code = code
        self.message = message


def now():
    return datetime.now(timezone.utc)


def ensure_dir():
    VAULT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(VAULT_DIR, 0o700)


def write_private(path, data):
    """Atomically write bytes to path with mode 600."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            fd = -1
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if fd != -1:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def audit_log(action, key=None, result="ok"):
    """Append one line to the audit log. Never receives secret values."""
    parts = [now().isoformat(timespec="seconds"), action, key or "-", result]
    fd = os.open(AUDIT_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (" ".join(parts) + "\n").encode())
    finally:
        os.close(fd)


def derive_fernet(password, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password)))


def read_attempts():
    try:
        return int(ATTEMPTS_FILE.read_text().strip() or 0)
    except (OSError, ValueError):
        return 0


def register_failure(action):
    attempts = read_attempts() + 1
    if attempts >= MAX_ATTEMPTS:
        write_private(LOCKOUT_FILE, now().isoformat().encode())
        try:
            ATTEMPTS_FILE.unlink()
        except OSError:
            pass
        audit_log(action, result="auth_failed_lockout")
        raise VaultExit(AUTH_ERROR, "too many failed attempts: vault locked")
    write_private(ATTEMPTS_FILE, str(attempts).encode())
    audit_log(action, result="auth_failed")
    raise VaultExit(AUTH_ERROR, "authentication failed")


def clear_failures():
    try:
        ATTEMPTS_FILE.unlink()
    except OSError:
        pass


def check_lockout(action):
    if LOCKOUT_FILE.exists():
        audit_log(action, result="locked_out")
        raise VaultExit(AUTH_ERROR, f"vault is locked out; remove {LOCKOUT_FILE} to unlock")


def load_vault(password, action):
    """Return (salt, entries). Counts wrong passwords toward lockout."""
    if not VAULT_FILE.exists():
        return os.urandom(SALT_LEN), {}
    blob = VAULT_FILE.read_bytes()
    if len(blob) <= len(MAGIC) + SALT_LEN or not blob.startswith(MAGIC):
        raise VaultExit(USER_ERROR, "vault file is corrupt")
    salt = blob[len(MAGIC):len(MAGIC) + SALT_LEN]
    token = blob[len(MAGIC) + SALT_LEN:]
    try:
        plain = derive_fernet(password, salt).decrypt(token)
    except InvalidToken:
        register_failure(action)
    try:
        entries = json.loads(plain)
    except ValueError:
        raise VaultExit(USER_ERROR, "vault contents are corrupt")
    clear_failures()
    return salt, entries


def save_vault(password, salt, entries):
    token = derive_fernet(password, salt).encrypt(json.dumps(entries).encode())
    write_private(VAULT_FILE, MAGIC + salt + token)


def is_expired(entry):
    try:
        exp = datetime.fromisoformat(entry["expires"])
    except (KeyError, ValueError, TypeError):
        return True  # unreadable expiry: fail closed
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return now() >= exp


def new_entry(value, ttl):
    return {"value": value, "expires": (now() + timedelta(days=ttl)).isoformat()}


# ---------- argument validation ----------

def valid_key(raw):
    if not KEY_RE.fullmatch(raw):
        raise VaultExit(USER_ERROR, "invalid key: must match [a-zA-Z0-9_]{1,64}")
    return raw.lower()


def valid_value(raw):
    if raw is None:
        data = sys.stdin.buffer.read()
        if data.endswith(b"\n"):
            data = data[:-1]
    else:
        try:
            data = raw.encode("utf-8")
        except UnicodeEncodeError:
            raise VaultExit(USER_ERROR, "value is not valid UTF-8")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise VaultExit(USER_ERROR, "value is not valid UTF-8")
    if len(data) > MAX_VALUE_BYTES:
        raise VaultExit(USER_ERROR, f"value exceeds {MAX_VALUE_BYTES} bytes")
    return text


def valid_ttl(ttl):
    if not 1 <= ttl <= MAX_TTL_DAYS:
        raise VaultExit(USER_ERROR, f"--ttl must be between 1 and {MAX_TTL_DAYS} days")
    return ttl


# ---------- commands ----------

def cmd_set(args, password):
    key = valid_key(args.key)
    value = valid_value(args.value)
    ttl = valid_ttl(args.ttl)
    salt, entries = load_vault(password, "set")
    entries[key] = new_entry(value, ttl)
    save_vault(password, salt, entries)
    audit_log("set", key)
    return OK


def cmd_get(args, password):
    key = valid_key(args.key)
    _, entries = load_vault(password, "get")
    entry = entries.get(key)
    if entry is None:
        audit_log("get", key, "not_found")
        raise VaultExit(USER_ERROR, "no such key")
    if is_expired(entry):
        audit_log("get", key, "expired")
        raise VaultExit(EXPIRED, "key has expired")
    audit_log("get", key)
    sys.stdout.write(entry["value"] + "\n")
    return OK


def cmd_list(args, password):
    _, entries = load_vault(password, "list")
    for key in sorted(entries):
        entry = entries[key]
        if is_expired(entry):
            shown = "[EXPIRED]"
        else:
            value = entry["value"]
            # Values of 4 chars or fewer would be fully revealed by a prefix.
            shown = (value[:4] if len(value) > 4 else "") + "***"
        print(f"{key}\t{shown}\t{entry.get('expires', '?')}")
    audit_log("list")
    return OK


def cmd_delete(args, password):
    key = valid_key(args.key)
    salt, entries = load_vault(password, "delete")
    if key not in entries:
        audit_log("delete", key, "not_found")
        raise VaultExit(USER_ERROR, "no such key")
    del entries[key]
    save_vault(password, salt, entries)
    audit_log("delete", key)
    return OK


def cmd_rotate(args, password):
    key = valid_key(args.key)
    value = valid_value(args.value)
    ttl = valid_ttl(args.ttl)
    salt, entries = load_vault(password, "rotate")
    if key not in entries:
        audit_log("rotate", key, "not_found")
        raise VaultExit(USER_ERROR, "no such key")
    entries[key] = new_entry(value, ttl)
    save_vault(password, salt, entries)
    audit_log("rotate", key)
    return OK


def cmd_audit(args, password):
    if VAULT_FILE.exists():
        load_vault(password, "audit")
    audit_log("audit")
    lines = AUDIT_FILE.read_text(errors="replace").splitlines()
    for line in lines[-AUDIT_TAIL:]:
        print(line)
    return OK


COMMANDS = {
    "set": cmd_set,
    "get": cmd_get,
    "list": cmd_list,
    "delete": cmd_delete,
    "rotate": cmd_rotate,
    "audit": cmd_audit,
}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse defaults to exit 2, which is reserved for auth/lockout.
        self.print_usage(sys.stderr)
        print(f"vault: error: {message}", file=sys.stderr)
        raise SystemExit(USER_ERROR)


def build_parser():
    p = Parser(prog="vault", description="Secret vault. Master password: $VAULT_MASTER_KEY")
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)

    s = sub.add_parser("set", help="store a value (reads stdin if VALUE omitted)")
    s.add_argument("key")
    s.add_argument("value", nargs="?")
    s.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, metavar="DAYS")

    g = sub.add_parser("get", help="print a value")
    g.add_argument("key")

    sub.add_parser("list", help="list keys with masked values")

    d = sub.add_parser("delete", help="delete a key")
    d.add_argument("key")

    r = sub.add_parser("rotate", help="replace the value of an existing key")
    r.add_argument("key")
    r.add_argument("value", nargs="?")
    r.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, metavar="DAYS")

    sub.add_parser("audit", help="show the last 20 audit log lines")
    return p


def run(argv):
    args = build_parser().parse_args(argv)
    password = os.environb.get(b"VAULT_MASTER_KEY")
    if not password:
        raise VaultExit(AUTH_ERROR, "VAULT_MASTER_KEY is not set")
    ensure_dir()
    with open(LOCK_FILE, "a") as lock:
        os.chmod(LOCK_FILE, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        check_lockout(args.command)
        return COMMANDS[args.command](args, password)


def main(argv=None):
    try:
        code = run(sys.argv[1:] if argv is None else argv)
        sys.stdout.flush()
        return code
    except VaultExit as e:
        if e.message:
            print(f"vault: {e.message}", file=sys.stderr)
        return e.code
    except OSError as e:
        # Report only the errno text; never include data.
        print(f"vault: I/O error: {e.strerror or type(e).__name__}", file=sys.stderr)
        return USER_ERROR
    except KeyboardInterrupt:
        return USER_ERROR


if __name__ == "__main__":
    sys.exit(main())
