# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Secret Vault CLI
- Objective: Single-file Python CLI (vault.py) that stores secrets encrypted with Fernet under a password-derived key, with TTL, audit log, lockout and strict file permissions.

## Non-Negotiable Guardrails
- Master password is read only from VAULT_MASTER_KEY, never from argv.
- No dependency beyond the standard library and cryptography.
- No secret value ever appears in the audit log, stderr or list output beyond the first 4 characters.
- No network access, no remote sync, no multi-user support.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user instead of guessing.
- If a test needs a value in stderr or the audit log to pass, stop; that violates the spec.

## Success Criteria
- All 14 requirements are demonstrated by passing unittest boundary tests run against vault.py as a subprocess with a temporary HOME.

## Assumptions
- Vault files live in ~/.vault/ resolved from the HOME directory: vault.enc, audit.log and .lockout.
- CLI shape: vault.py set KEY VALUE [--ttl DAYS], get KEY, list, delete KEY, rotate KEY VALUE [--ttl DAYS], audit.
- rotate replaces the value of an existing key and resets its expiry; it does not change the master password.
- Lockout counts consecutive wrong passwords in .lockout; while .lockout reaches 3 failures every command exits 2 without trying decryption; a correct password resets the counter.
- A missing VAULT_MASTER_KEY, bad key name, oversized value, missing key, or bad --ttl is a user error (exit 1).
- The audit log records timestamp, command and key name only; get on a missing key exits 1.
- audit itself appends an audit line and then prints the last 20 lines; it needs a correct master password like every command.
- File header layout is the 16-byte salt followed by the Fernet token.

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
