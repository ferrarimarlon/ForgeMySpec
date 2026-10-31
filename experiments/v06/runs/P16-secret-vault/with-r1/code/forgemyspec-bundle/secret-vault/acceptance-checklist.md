# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file Python CLI (vault.py) that stores secrets encrypted with Fernet under a password-derived key, with TTL, audit log, lockout and strict file permissions.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All 14 requirements are demonstrated by passing unittest boundary tests run against vault.py as a subprocess with a temporary HOME.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all boundary tests passing.
- [ ] Gate report ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user instead of guessing.
- [ ] If a test needs a value in stderr or the audit log to pass, stop; that violates the spec.
