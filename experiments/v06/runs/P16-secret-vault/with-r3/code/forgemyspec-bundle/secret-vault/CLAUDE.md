# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Secret Vault CLI
- Objective: A single-file Python CLI (vault.py) that stores secrets in an encrypted file under ~/.vault/, with TTL expiry, lockout after wrong passwords, and an audit log that never contains values.

## Non-Negotiable Guardrails
- No password option or prompt on the CLI; the master password is read only from VAULT_MASTER_KEY.
- No crypto other than Fernet with PBKDF2HMAC SHA-256; no custom ciphers.
- No network access, no extra dependencies beyond cryptography, no second source file.
- No value text in audit.log, stderr or exception messages.
- No automatic lockout reset and no key export or import commands.

## Decision Rules
- Stop and ask the user if a requirement conflicts with another or cannot be tested.
- Any change to behavior outside the obligations is a spec amendment.

## Success Criteria
- All boundary tests in tests/test_vault.py pass.
- The vault file contains no plaintext value and starts with a 16-byte salt.
- File modes are 600 for vault.enc and 700 for ~/.vault/.

## Assumptions
- Vault lives at ~/.vault/vault.enc; audit log at ~/.vault/audit.log; lockout marker at ~/.vault/.lockout; failed-attempt counter at ~/.vault/.attempts (reset on a correct password).
- Usage: vault.py set KEY VALUE [--ttl DAYS]; get KEY; list; delete KEY; rotate KEY NEWVALUE [--ttl DAYS]; audit. Values are positional arguments (only the master password is barred from the CLI).
- File format: 16-byte salt header followed by the Fernet token of a JSON object mapping key to {value, expires}.
- While .lockout exists every command exits 2 without trying a password; removing it is a manual action by the user.
- A missing VAULT_MASTER_KEY exits 2. A missing key on get/delete exits 1. Invalid key, oversized value, non-integer or negative TTL exit 1.
- rotate replaces the value of an existing key and resets expiry from --ttl (default 90). list shows expired entries as 'expired' without any value characters.
- Every command appends one line (UTC timestamp, command, key name, outcome) to audit.log; the audit command also prints its last 20 lines.

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
