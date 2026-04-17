# CLAUDE.md — Secret Vault CLI

## Objective
Single-file `vault.py`: encrypted CLI secret store with master-password auth, TTL, audit log, lockout.

## Hard Constraints (never violate)
- Master password: ONLY from `os.environ["VAULT_MASTER_KEY"]` — no CLI arg, no prompt.
- Encryption: `Fernet` + `PBKDF2HMAC(SHA256, 200000)`. Salt = first 16 bytes of `vault.enc`.
- Key regex: `^[a-zA-Z0-9_]{1,64}$`, normalized lowercase.
- Value max: 4096 bytes UTF-8.
- `get` on expired key: exit 3, stderr only — **nothing to stdout**.
- `list`: `value[:4] + "***"` — never full value.
- `audit.log`: timestamp | action | key | OK/FAIL — **never the value**.
- `vault.enc` → chmod 600. `~/.vault/` → chmod 700.
- No `eval()`, no `shell=True`, no `pickle`.

## File Layout
```
~/.vault/
├── vault.enc      # 16-byte salt + Fernet(JSON)
├── audit.log      # append-only, no values
├── .lockout       # ISO expiry timestamp (presence = locked)
└── .fails         # integer fail count
```

## Internal Data Structure
```json
{ "api_key": { "value": "abc123", "expiry": "2026-07-16T12:00:00" } }
```

## Key Functions (implement in order: A1→A11, validate A12)
1. `_derive_key(password, salt)` → Fernet key
2. `_load_vault()` / `_save_vault(data)` → decrypt/encrypt vault.enc
3. `_check_lockout()` → exit 2 if .lockout unexpired
4. `_record_fail()` → increment .fails; if ≥3 write .lockout
5. `_audit(action, key, result)` → append to audit.log
6. `cmd_set / cmd_get / cmd_list / cmd_delete / cmd_rotate / cmd_audit`

## Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Key error (not found, invalid format, value too large) |
| 2 | Auth/lockout error (wrong password, vault locked, env var missing) |
| 3 | Key expired |

## Known Pitfalls
- `PBKDF2HMAC` instances are **not reusable** — create a new one per `derive()` call.
- Fernet raises `InvalidToken` on wrong password or corrupt file — catch it, call `_record_fail()`.
- `bool` check for lockout: compare `datetime.utcnow() < lockout_expiry`, not file existence alone (file may be stale).
- Do NOT use `os.system` or `subprocess` for chmod — use `os.chmod`.
- Reset `.fails` to 0 on every successful decrypt.
