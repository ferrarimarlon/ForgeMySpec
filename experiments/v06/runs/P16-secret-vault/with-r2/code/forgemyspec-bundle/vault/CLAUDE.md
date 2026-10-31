# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Secret Vault CLI
- Objective: A single-file Python CLI (vault.py) that stores TTL-bound secrets encrypted with Fernet under a PBKDF2-derived key, with audit log, lockout and strict exit codes.

## Non-Negotiable Guardrails
- Not built: no config file, no import/export, no multiple vaults, no master-password change command, no unlock command.
- The master password is read only from VAULT_MASTER_KEY; no CLI flag carries it.
- Values and the master password never appear in audit.log or stderr.
- Single file vault.py; third-party dependency limited to cryptography.

## Decision Rules
- If a requirement conflicts with another (for example value[:4] versus never the full value), stop and record the resolution as an assumption.
- Stop and ask before adding any command or option beyond the six listed.

## Success Criteria
- All boundary tests in tests/test_vault.py pass.
- Exit codes are 0 ok, 1 user error, 2 auth or lockout, 3 expired.

## Assumptions
- The vault lives at ~/.vault/vault.enc; ~ comes from the HOME environment variable so tests can redirect it.
- File layout: magic header, the 16-byte salt, then one Fernet token holding a JSON map of key to {value, expires}. The first `set` creates the vault with the current master password.
- Values are passed as an optional positional argument of set and rotate; when omitted they are read from stdin (keeps them out of shell history).
- Wrong-password count is persisted in ~/.vault/.failcount, reset on success; the third consecutive failure creates ~/.vault/.lockout. While .lockout exists every command that needs the password exits 2 without trying. Only the user deletes .lockout.
- A missing or empty VAULT_MASTER_KEY exits 2 and does not count as a failed attempt.
- list on a value of 4 characters or fewer shows at most len-1 characters before *** so the full value is never shown (deviation from a literal value[:4]); expired entries in list show [expired] and no value characters.
- Every command except audit appends one line (UTC ISO timestamp, command, key name, exit outcome) to audit.log; audit needs no password and prints the last 20 lines. Key names are logged, values never.
- --ttl must be a positive integer number of days; otherwise exit 1. rotate replaces the value and recomputes expiry from --ttl (default 90).
- Lookup is case-insensitive because keys are lowercased on input. Unknown key on get or delete exits 1.

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- (record stable architecture or policy decisions here)

## Known Pitfalls
- (record recurring implementation failure modes here)
