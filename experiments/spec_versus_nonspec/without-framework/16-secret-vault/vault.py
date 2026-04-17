#!/usr/bin/env python3
"""
vault.py — Encrypted CLI secret vault.

Vault file:    ~/.vault/vault.enc
Audit log:     ~/.vault/audit.log
Lockout file:  ~/.vault/.lockout

Master password is read exclusively from the VAULT_MASTER_KEY environment variable.
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency guard — only `cryptography` is allowed
# ---------------------------------------------------------------------------
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except ImportError:
    print("ERROR: 'cryptography' package is required. Install with: pip install cryptography", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VAULT_DIR = Path.home() / ".vault"
VAULT_FILE = VAULT_DIR / "vault.enc"
AUDIT_LOG = VAULT_DIR / "audit.log"
LOCKOUT_FILE = VAULT_DIR / ".lockout"

PBKDF2_ITERATIONS = 200_000
SALT_SIZE = 16
MAX_FAILED_ATTEMPTS = 3
LOCKOUT_DURATION_MINUTES = 5
DEFAULT_TTL_DAYS = 90
MAX_VALUE_BYTES = 4096
KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_]{1,64}$')


# ---------------------------------------------------------------------------
# Directory / file setup
# ---------------------------------------------------------------------------

def ensure_vault_dir() -> None:
    """Create ~/.vault with mode 700 if it does not exist."""
    VAULT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Enforce permissions even if dir already existed
    VAULT_DIR.chmod(0o700)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet-compatible key from *password* and *salt*."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


# ---------------------------------------------------------------------------
# Vault file I/O
# ---------------------------------------------------------------------------

def _load_raw() -> tuple[bytes, dict]:
    """
    Return (salt, plaintext_dict) by reading and decrypting the vault file.

    Raises FileNotFoundError if the vault has never been initialised.
    Raises InvalidToken on wrong password (after lockout tracking).
    """
    data = VAULT_FILE.read_bytes()
    # First 16 bytes = salt, remainder = Fernet ciphertext
    salt = data[:SALT_SIZE]
    ciphertext = data[SALT_SIZE:]
    master = _get_master_key()
    fernet_key = derive_key(master, salt)
    f = Fernet(fernet_key)
    plaintext = f.decrypt(ciphertext)          # raises InvalidToken on wrong key
    return salt, json.loads(plaintext.decode("utf-8"))


def _save_raw(salt: bytes, vault: dict) -> None:
    """Encrypt *vault* with *salt* + master key and write atomically."""
    master = _get_master_key()
    fernet_key = derive_key(master, salt)
    f = Fernet(fernet_key)
    plaintext = json.dumps(vault).encode("utf-8")
    ciphertext = f.encrypt(plaintext)
    tmp = VAULT_FILE.with_suffix(".tmp")
    tmp.write_bytes(salt + ciphertext)
    tmp.chmod(0o600)
    tmp.rename(VAULT_FILE)
    # Ensure permissions on the (possibly pre-existing) vault file
    VAULT_FILE.chmod(0o600)


def load_vault() -> tuple[bytes, dict]:
    """
    Load the vault, handling auth failures with lockout logic.
    On success resets the failed-attempt counter stored in the vault dir.
    """
    _check_lockout()
    try:
        salt, vault = _load_raw()
        _reset_failed_attempts()
        return salt, vault
    except (InvalidToken, Exception) as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        # Wrong password path
        count = _increment_failed_attempts()
        if count >= MAX_FAILED_ATTEMPTS:
            expiry = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            LOCKOUT_FILE.write_text(expiry.isoformat())
            _reset_failed_attempts()
            print(f"Vault locked until {expiry.astimezone().strftime('%H:%M:%S')}", file=sys.stderr)
            sys.exit(2)
        remaining = MAX_FAILED_ATTEMPTS - count
        print(f"Wrong master password. {remaining} attempt(s) remaining before lockout.", file=sys.stderr)
        sys.exit(2)


def init_vault() -> tuple[bytes, dict]:
    """
    Return (salt, vault) for a brand-new vault, or load existing one.
    If vault file does not exist, create empty vault encrypted with a fresh salt.
    """
    if not VAULT_FILE.exists():
        salt = os.urandom(SALT_SIZE)
        vault: dict = {"secrets": {}, "failed_attempts": 0}
        _save_raw(salt, vault)
        return salt, vault
    return load_vault()


# ---------------------------------------------------------------------------
# Lockout helpers
# ---------------------------------------------------------------------------

def _check_lockout() -> None:
    if not LOCKOUT_FILE.exists():
        return
    expiry_str = LOCKOUT_FILE.read_text().strip()
    try:
        expiry = datetime.fromisoformat(expiry_str)
    except ValueError:
        LOCKOUT_FILE.unlink(missing_ok=True)
        return
    now = datetime.now(timezone.utc)
    if now < expiry:
        local_expiry = expiry.astimezone()
        print(f"Vault locked until {local_expiry.strftime('%H:%M:%S')}", file=sys.stderr)
        sys.exit(2)
    # Lockout expired
    LOCKOUT_FILE.unlink(missing_ok=True)


def _failed_attempts_file() -> Path:
    return VAULT_DIR / ".failed_attempts"


def _increment_failed_attempts() -> int:
    p = _failed_attempts_file()
    count = int(p.read_text()) if p.exists() else 0
    count += 1
    p.write_text(str(count))
    return count


def _reset_failed_attempts() -> None:
    p = _failed_attempts_file()
    p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Master key helper
# ---------------------------------------------------------------------------

def _get_master_key() -> str:
    key = os.environ.get("VAULT_MASTER_KEY", "")
    if not key:
        print("ERROR: VAULT_MASTER_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(2)
    return key


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _audit(action: str, key: str, status: str) -> None:
    """Append one line to audit.log. Never writes secret values."""
    ensure_vault_dir()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"{timestamp}\t{action}\t{key}\t{status}\n"
    with AUDIT_LOG.open("a") as fh:
        fh.write(line)


# ---------------------------------------------------------------------------
# Key name validation
# ---------------------------------------------------------------------------

def _validate_key(name: str) -> str:
    """Return lowercase key or exit 1 with an error message."""
    if not KEY_PATTERN.match(name):
        print(f"ERROR: Key name '{name}' is invalid. Use alphanumeric characters and underscores, 1–64 chars.", file=sys.stderr)
        sys.exit(1)
    return name.lower()


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_set(args: argparse.Namespace) -> None:
    # Validate and normalise key name first so audit entries use the canonical form.
    key = _validate_key(args.key)
    value: str = args.value
    if len(value.encode("utf-8")) > MAX_VALUE_BYTES:
        _audit("set", key, "FAIL")
        print(f"ERROR: Value exceeds maximum of {MAX_VALUE_BYTES} bytes.", file=sys.stderr)
        sys.exit(1)
    ttl_days: int = args.ttl
    expiry = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(timespec="seconds")

    salt, vault = init_vault()
    vault.setdefault("secrets", {})
    vault["secrets"][key] = {
        "value": value,
        "expiry": expiry,
    }
    _save_raw(salt, vault)
    _audit("set", key, "OK")
    print(f"Key '{key}' stored (expires {expiry}).")


def cmd_get(args: argparse.Namespace) -> None:
    key = _validate_key(args.key)
    salt, vault = load_vault()
    secrets = vault.get("secrets", {})

    if key not in secrets:
        _audit("get", key, "FAIL")
        print(f"ERROR: Key '{key}' not found.", file=sys.stderr)
        sys.exit(1)

    entry = secrets[key]
    expiry = datetime.fromisoformat(entry["expiry"])
    now = datetime.now(timezone.utc)

    if now >= expiry:
        _audit("get", key, "FAIL")
        print(f"ERROR: Key '{key}' has expired (expired {entry['expiry']}).", file=sys.stderr)
        sys.exit(3)

    _audit("get", key, "OK")
    # Print value to stdout only — no extra decoration
    print(entry["value"])


def cmd_list(args: argparse.Namespace) -> None:
    try:
        salt, vault = init_vault()
    except Exception:
        _audit("list", "", "FAIL")
        raise

    secrets = vault.get("secrets", {})
    _audit("list", "", "OK")

    if not secrets:
        print("(vault is empty)")
        return

    now = datetime.now(timezone.utc)
    print(f"{'KEY':<30}  {'EXPIRY':<25}  PREVIEW")
    print("-" * 70)
    for k, entry in sorted(secrets.items()):
        expiry_str = entry["expiry"]
        expiry_dt = datetime.fromisoformat(expiry_str)
        status = " [EXPIRED]" if now >= expiry_dt else ""
        preview = entry["value"][:4] + "***"
        print(f"{k:<30}  {expiry_str:<25}  {preview}{status}")


def cmd_delete(args: argparse.Namespace) -> None:
    key = _validate_key(args.key)
    salt, vault = load_vault()
    secrets = vault.get("secrets", {})

    if key not in secrets:
        _audit("delete", key, "FAIL")
        print(f"ERROR: Key '{key}' not found.", file=sys.stderr)
        sys.exit(1)

    del secrets[key]
    _save_raw(salt, vault)
    _audit("delete", key, "OK")
    print(f"Key '{key}' deleted.")


def cmd_rotate(args: argparse.Namespace) -> None:
    key = _validate_key(args.key)
    new_value: str = args.new_value

    if len(new_value.encode("utf-8")) > MAX_VALUE_BYTES:
        _audit("rotate", key, "FAIL")
        print(f"ERROR: New value exceeds maximum of {MAX_VALUE_BYTES} bytes.", file=sys.stderr)
        sys.exit(1)

    salt, vault = load_vault()
    secrets = vault.get("secrets", {})

    if key not in secrets:
        _audit("rotate", key, "FAIL")
        print(f"ERROR: Key '{key}' not found. Cannot rotate a non-existent key.", file=sys.stderr)
        sys.exit(1)

    # Preserve existing TTL (expiry) by keeping the same expiry date, or
    # compute a fresh one if the entry is missing an expiry field.
    old_entry = secrets[key]
    ttl_days = args.ttl if args.ttl is not None else DEFAULT_TTL_DAYS
    if args.ttl is not None:
        expiry = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(timespec="seconds")
    else:
        # Keep existing expiry on rotate if --ttl not specified
        expiry = old_entry.get("expiry", (datetime.now(timezone.utc) + timedelta(days=DEFAULT_TTL_DAYS)).isoformat(timespec="seconds"))

    secrets[key] = {"value": new_value, "expiry": expiry}
    _save_raw(salt, vault)
    _audit("rotate", key, "OK")
    print(f"Key '{key}' rotated.")


def cmd_audit(args: argparse.Namespace) -> None:
    # Log the audit command itself
    _audit("audit", "", "OK")
    if not AUDIT_LOG.exists():
        print("(audit log is empty)")
        return
    lines = AUDIT_LOG.read_text().splitlines()
    last20 = lines[-20:]
    print(f"{'TIMESTAMP':<27}  {'ACTION':<10}  {'KEY':<30}  STATUS")
    print("-" * 80)
    for line in last20:
        parts = line.split("\t")
        if len(parts) == 4:
            print(f"{parts[0]:<27}  {parts[1]:<10}  {parts[2]:<30}  {parts[3]}")
        else:
            print(line)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Encrypted CLI secret vault. Master password via VAULT_MASTER_KEY env var.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # set
    p_set = sub.add_parser("set", help="Store a secret")
    p_set.add_argument("key", help="Key name (alphanumeric + underscores, max 64 chars)")
    p_set.add_argument("value", help="Secret value (max 4096 bytes UTF-8)")
    p_set.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, metavar="DAYS",
                       help=f"Time-to-live in days (default: {DEFAULT_TTL_DAYS})")

    # get
    p_get = sub.add_parser("get", help="Retrieve a secret")
    p_get.add_argument("key")

    # list
    sub.add_parser("list", help="List all keys with metadata")

    # delete
    p_del = sub.add_parser("delete", help="Remove a secret")
    p_del.add_argument("key")

    # rotate
    p_rot = sub.add_parser("rotate", help="Atomically replace a secret's value")
    p_rot.add_argument("key")
    p_rot.add_argument("new_value", metavar="NEW_VALUE")
    p_rot.add_argument("--ttl", type=int, default=None, metavar="DAYS",
                       help="New TTL in days (default: keep existing expiry)")

    # audit
    sub.add_parser("audit", help="Show last 20 audit log entries")

    return parser


def main() -> None:
    ensure_vault_dir()
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "set": cmd_set,
        "get": cmd_get,
        "list": cmd_list,
        "delete": cmd_delete,
        "rotate": cmd_rotate,
        "audit": cmd_audit,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
