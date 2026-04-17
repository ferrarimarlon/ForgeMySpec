# Acceptance Checklist — Secret Vault CLI

## Functional
- [ ] `set KEY VALUE` stores secret; `get KEY` returns exact value
- [ ] `set` with invalid key (spaces, special chars) → exit 1, no vault change
- [ ] `set` with value > 4096 bytes → exit 1
- [ ] `get` on missing key → exit 1
- [ ] `get` on expired key → exit 3, stdout empty, stderr has message
- [ ] `list` shows `key | expiry | XXXX***` — never full value
- [ ] `delete` on existing key → exit 0, key gone
- [ ] `delete` on missing key → exit 1
- [ ] `rotate KEY NEW_VALUE` on existing key → exit 0, value updated
- [ ] `rotate` on missing key → exit 1, vault unchanged
- [ ] `audit` prints last 20 lines from audit.log

## Security
- [ ] `audit.log` contains no secret values after set/get/rotate
- [ ] `vault.enc` has permissions 0o600
- [ ] `~/.vault/` has permissions 0o700
- [ ] Running without `VAULT_MASTER_KEY` set → exit 2
- [ ] 3 wrong passwords → `.lockout` file created
- [ ] 4th attempt within lockout window → exit 2 with "Vault locked until HH:MM:SS"
- [ ] Correct password after lockout expires → vault accessible again (`.lockout` ignored)
- [ ] list output: confirmed no full value visible even for short values

## Code Quality
- [ ] No `eval()` anywhere
- [ ] No `subprocess(shell=True)`
- [ ] `PBKDF2HMAC` instance created fresh per `derive()` call
- [ ] `InvalidToken` exception caught and handled (wrong password path)
- [ ] `.fails` counter reset to 0 on successful auth
