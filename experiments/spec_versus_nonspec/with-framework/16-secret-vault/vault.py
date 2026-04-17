#!/usr/bin/env python3
"""
vault.py — Single-file encrypted CLI secret store.
Dependencies: cryptography (Fernet + PBKDF2HMAC)
"""

import argparse
import json
import os
import re
import sys
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VAULT_DIR = Path.home() / ".vault"
VAULT_ENC = VAULT_DIR / "vault.enc"
AUDIT_LOG = VAULT_DIR / "audit.log"
LOCKOUT_FILE = VAULT_DIR / ".lockout"
FAILS_FILE = VAULT_DIR / ".fails"

SALT_SIZE = 16
KDF_ITERATIONS = 200_000
TTL_DEFAULT_DAYS = 90
MAX_VALUE_BYTES = 4096
KEY_REGEX = re.compile(r"^[a-zA-Z0-9_]{1,64}$")
MAX_LOCKOUT_FAILS = 3
LOCKOUT_SECONDS = 300
AUDIT_TAIL_LINES = 20

# ---------------------------------------------------------------------------
# A1 — Key derivation
# ---------------------------------------------------------------------------

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from password + salt via PBKDF2HMAC."""
    # PBKDF2HMAC instances are NOT reusable; create a fresh one each call.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    raw_key = kdf.derive(password.encode("utf-8"))
    return urlsafe_b64encode(raw_key)  # Fernet expects URL-safe base64


# ---------------------------------------------------------------------------
# A2 — Load / save vault
# ---------------------------------------------------------------------------

def _ensure_vault_dir() -> None:
    """Create ~/.vault/ with chmod 700 if it does not exist."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(VAULT_DIR, 0o700)


def _load_vault(password: str) -> dict:
    """
    Read vault.enc (16-byte salt + Fernet ciphertext), decrypt, return dict.
    Raises InvalidToken on wrong password or corrupt file.
    Returns empty dict if vault.enc does not exist yet.
    """
    _ensure_vault_dir()

    if not VAULT_ENC.exists():
        return {}

    raw = VAULT_ENC.read_bytes()
    if len(raw) < SALT_SIZE:
        raise ValueError("vault.enc is corrupt (too short).")

    salt = raw[:SALT_SIZE]
    ciphertext = raw[SALT_SIZE:]
    key = _derive_key(password, salt)
    fernet = Fernet(key)
    plaintext = fernet.decrypt(ciphertext)  # raises InvalidToken on failure
    return json.loads(plaintext.decode("utf-8"))


def _save_vault(data: dict, password: str) -> None:
    """
    Encrypt dict and write 16-byte salt + Fernet ciphertext to vault.enc.
    Preserves existing salt if vault.enc already exists; generates new salt otherwise.
    Sets chmod 600 on vault.enc.
    """
    _ensure_vault_dir()

    # Reuse existing salt to avoid key-rotation side effects.
    if VAULT_ENC.exists():
        existing = VAULT_ENC.read_bytes()
        salt = existing[:SALT_SIZE] if len(existing) >= SALT_SIZE else os.urandom(SALT_SIZE)
    else:
        salt = os.urandom(SALT_SIZE)

    key = _derive_key(password, salt)
    fernet = Fernet(key)
    plaintext = json.dumps(data).encode("utf-8")
    ciphertext = fernet.encrypt(plaintext)

    VAULT_ENC.write_bytes(salt + ciphertext)
    os.chmod(VAULT_ENC, 0o600)


# ---------------------------------------------------------------------------
# A3 — Lockout / fail counter
# ---------------------------------------------------------------------------

def _check_lockout() -> None:
    """Exit 2 with a friendly message if .lockout file exists and has not expired."""
    if not LOCKOUT_FILE.exists():
        return
    try:
        expiry_str = LOCKOUT_FILE.read_text().strip()
        expiry = datetime.fromisoformat(expiry_str)
        # Normalize: if expiry has no tzinfo, treat as UTC
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        if now < expiry:
            expiry_local = expiry.astimezone()  # convert to local time for display
            print(
                f"Vault locked until {expiry_local.strftime('%H:%M:%S')}",
                file=sys.stderr,
            )
            sys.exit(2)
        else:
            # Lockout has expired — clean up
            LOCKOUT_FILE.unlink(missing_ok=True)
            FAILS_FILE.unlink(missing_ok=True)
    except (ValueError, OSError):
        # Corrupt lockout file — remove it and proceed
        LOCKOUT_FILE.unlink(missing_ok=True)


def _get_fail_count() -> int:
    """Read current consecutive fail count from .fails."""
    try:
        return int(FAILS_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _record_fail() -> None:
    """
    Increment .fails counter. If count reaches MAX_LOCKOUT_FAILS,
    write .lockout with expiry and exit 2.
    """
    _ensure_vault_dir()
    count = _get_fail_count() + 1
    FAILS_FILE.write_text(str(count))

    if count >= MAX_LOCKOUT_FAILS:
        expiry = datetime.now(tz=timezone.utc) + timedelta(seconds=LOCKOUT_SECONDS)
        LOCKOUT_FILE.write_text(expiry.isoformat())
        expiry_local = expiry.astimezone()
        print(
            f"Vault locked until {expiry_local.strftime('%H:%M:%S')}",
            file=sys.stderr,
        )
        sys.exit(2)


def _reset_fails() -> None:
    """Reset fail counter on successful authentication."""
    FAILS_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# A4 — Audit log
# ---------------------------------------------------------------------------

def _audit(action: str, key: str, result: str) -> None:
    """
    Append 'YYYY-MM-DD HH:MM:SS | ACTION | key | OK/FAIL' to audit.log.
    Never includes secret values.
    """
    _ensure_vault_dir()
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {action.upper()} | {key} | {result}\n"
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


# ---------------------------------------------------------------------------
# A5 — cmd_set
# ---------------------------------------------------------------------------

def cmd_set(args, password: str) -> None:
    key_raw: str = args.key
    value: str = args.value
    ttl_days: int = args.ttl

    # Validate key format before touching the vault
    if not KEY_REGEX.match(key_raw):
        print(
            f"Invalid key '{key_raw}'. Keys must match ^[a-zA-Z0-9_]{{1,64}}$.",
            file=sys.stderr,
        )
        sys.exit(1)

    key = key_raw.lower()

    # Validate value size
    value_bytes = value.encode("utf-8")
    if len(value_bytes) > MAX_VALUE_BYTES:
        print(
            f"Value too large: {len(value_bytes)} bytes (max {MAX_VALUE_BYTES}).",
            file=sys.stderr,
        )
        sys.exit(1)

    _check_lockout()

    try:
        data = _load_vault(password)
        _reset_fails()
    except InvalidToken:
        _audit("SET", key, "FAIL")
        _record_fail()
        print("Wrong master password.", file=sys.stderr)
        sys.exit(2)

    expiry = (datetime.now(tz=timezone.utc) + timedelta(days=ttl_days)).isoformat()
    data[key] = {"value": value, "expiry": expiry}
    _save_vault(data, password)
    _audit("SET", key, "OK")


# ---------------------------------------------------------------------------
# A6 — cmd_get
# ---------------------------------------------------------------------------

def cmd_get(args, password: str) -> None:
    key_raw: str = args.key

    if not KEY_REGEX.match(key_raw):
        print(
            f"Invalid key '{key_raw}'. Keys must match ^[a-zA-Z0-9_]{{1,64}}$.",
            file=sys.stderr,
        )
        sys.exit(1)

    key = key_raw.lower()

    _check_lockout()

    try:
        data = _load_vault(password)
        _reset_fails()
    except InvalidToken:
        _audit("GET", key, "FAIL")
        _record_fail()
        print("Wrong master password.", file=sys.stderr)
        sys.exit(2)

    if key not in data:
        _audit("GET", key, "FAIL")
        print(f"Key '{key}' not found.", file=sys.stderr)
        sys.exit(1)

    entry = data[key]
    expiry_str = entry["expiry"]
    expiry = datetime.fromisoformat(expiry_str)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    if now >= expiry:
        _audit("GET", key, "FAIL")
        print(f"Key '{key}' has expired.", file=sys.stderr)
        sys.exit(3)

    # Print ONLY the value to stdout — nothing else
    print(entry["value"])
    _audit("GET", key, "OK")


# ---------------------------------------------------------------------------
# A7 — cmd_list
# ---------------------------------------------------------------------------

def cmd_list(args, password: str) -> None:
    _check_lockout()

    try:
        data = _load_vault(password)
        _reset_fails()
    except InvalidToken:
        _audit("LIST", "*", "FAIL")
        _record_fail()
        print("Wrong master password.", file=sys.stderr)
        sys.exit(2)

    if not data:
        print("(vault is empty)")
        _audit("LIST", "*", "OK")
        return

    for key in sorted(data.keys()):
        entry = data[key]
        value = entry["value"]
        expiry = entry["expiry"]
        # Mask: first 4 chars + *** (never full value)
        masked = (value[:4] if len(value) >= 4 else value) + "***"
        print(f"{key:<20} {expiry:<25} {masked}")

    _audit("LIST", "*", "OK")


# ---------------------------------------------------------------------------
# A8 — cmd_delete
# ---------------------------------------------------------------------------

def cmd_delete(args, password: str) -> None:
    key_raw: str = args.key

    if not KEY_REGEX.match(key_raw):
        print(
            f"Invalid key '{key_raw}'. Keys must match ^[a-zA-Z0-9_]{{1,64}}$.",
            file=sys.stderr,
        )
        sys.exit(1)

    key = key_raw.lower()

    _check_lockout()

    try:
        data = _load_vault(password)
        _reset_fails()
    except InvalidToken:
        _audit("DELETE", key, "FAIL")
        _record_fail()
        print("Wrong master password.", file=sys.stderr)
        sys.exit(2)

    if key not in data:
        _audit("DELETE", key, "FAIL")
        print(f"Key '{key}' not found.", file=sys.stderr)
        sys.exit(1)

    del data[key]
    _save_vault(data, password)
    _audit("DELETE", key, "OK")


# ---------------------------------------------------------------------------
# A9 — cmd_rotate
# ---------------------------------------------------------------------------

def cmd_rotate(args, password: str) -> None:
    key_raw: str = args.key
    new_value: str = args.new_value
    ttl_days: int = args.ttl

    if not KEY_REGEX.match(key_raw):
        print(
            f"Invalid key '{key_raw}'. Keys must match ^[a-zA-Z0-9_]{{1,64}}$.",
            file=sys.stderr,
        )
        sys.exit(1)

    key = key_raw.lower()

    value_bytes = new_value.encode("utf-8")
    if len(value_bytes) > MAX_VALUE_BYTES:
        print(
            f"Value too large: {len(value_bytes)} bytes (max {MAX_VALUE_BYTES}).",
            file=sys.stderr,
        )
        sys.exit(1)

    _check_lockout()

    try:
        data = _load_vault(password)
        _reset_fails()
    except InvalidToken:
        _audit("ROTATE", key, "FAIL")
        _record_fail()
        print("Wrong master password.", file=sys.stderr)
        sys.exit(2)

    if key not in data:
        _audit("ROTATE", key, "FAIL")
        print(f"Key '{key}' not found.", file=sys.stderr)
        sys.exit(1)

    expiry = (datetime.now(tz=timezone.utc) + timedelta(days=ttl_days)).isoformat()
    data[key] = {"value": new_value, "expiry": expiry}
    _save_vault(data, password)
    _audit("ROTATE", key, "OK")


# ---------------------------------------------------------------------------
# A10 — cmd_audit
# ---------------------------------------------------------------------------

def cmd_audit(args, password: str) -> None:
    # audit command reads the log — no vault decryption needed.
    if not AUDIT_LOG.exists():
        print("(audit log is empty)")
        return

    lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    for line in lines[-AUDIT_TAIL_LINES:]:
        print(line)


# ---------------------------------------------------------------------------
# A11 — Argparse wiring + entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Read VAULT_MASTER_KEY before any disk access
    password = os.environ.get("VAULT_MASTER_KEY")
    if password is None:
        print("VAULT_MASTER_KEY not set", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser(
        prog="vault",
        description="Encrypted CLI secret store.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # set
    p_set = subparsers.add_parser("set", help="Store a secret.")
    p_set.add_argument("key", help="Secret key name.")
    p_set.add_argument("value", help="Secret value.")
    p_set.add_argument(
        "--ttl",
        type=int,
        default=TTL_DEFAULT_DAYS,
        metavar="DAYS",
        help=f"Time-to-live in days (default: {TTL_DEFAULT_DAYS}).",
    )

    # get
    p_get = subparsers.add_parser("get", help="Retrieve a secret.")
    p_get.add_argument("key", help="Secret key name.")

    # list
    subparsers.add_parser("list", help="List all secrets (masked).")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a secret.")
    p_del.add_argument("key", help="Secret key name.")

    # rotate
    p_rot = subparsers.add_parser("rotate", help="Replace a secret's value.")
    p_rot.add_argument("key", help="Secret key name.")
    p_rot.add_argument("new_value", help="New secret value.")
    p_rot.add_argument(
        "--ttl",
        type=int,
        default=TTL_DEFAULT_DAYS,
        metavar="DAYS",
        help=f"New TTL in days (default: {TTL_DEFAULT_DAYS}).",
    )

    # audit
    subparsers.add_parser("audit", help="Print last 20 audit log lines.")

    args = parser.parse_args()

    dispatch = {
        "set": cmd_set,
        "get": cmd_get,
        "list": cmd_list,
        "delete": cmd_delete,
        "rotate": cmd_rotate,
        "audit": cmd_audit,
    }

    dispatch[args.command](args, password)


if __name__ == "__main__":
    main()
