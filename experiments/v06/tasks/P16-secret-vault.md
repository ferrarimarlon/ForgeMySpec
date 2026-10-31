Build a Secret Vault CLI in Python (single file vault.py; the `cryptography` package is allowed). Requirements:
1. The master password comes from the environment variable VAULT_MASTER_KEY, never from a CLI argument.
2. Encryption: Fernet with a key derived by PBKDF2HMAC SHA-256, 200,000 iterations, a random 16-byte salt stored in the file header.
3. Keys match [a-zA-Z0-9_]{1,64} and are stored lowercase.
4. Values are at most 4096 bytes of UTF-8.
5. TTL with --ttl DAYS (default 90); expiry stored as ISO-8601.
6. Commands: set, get, list, delete, rotate, audit.
7. get prints only the value to stdout; exit 3 if expired, and never print an expired value.
8. list shows value[:4] followed by *** and never the full value.
9. rotate exits 1 if the key does not exist.
10. audit appends to ~/.vault/audit.log and shows the last 20 lines.
11. Lockout: 3 wrong passwords create a .lockout file; exit 2.
12. Never write values to the audit log or stderr.
13. vault.enc is chmod 600 and ~/.vault/ is chmod 700.
14. Exit codes: 0 ok, 1 user error, 2 auth/lockout, 3 expired.
