# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python CLI (vault.py) that stores TTL-bound secrets encrypted with Fernet under a PBKDF2-derived key, with audit log, lockout and strict exit codes.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All boundary tests in tests/test_vault.py pass.
- [ ] Exit codes are 0 ok, 1 user error, 2 auth or lockout, 3 expired.

## Required Evidence
- [ ] Output of `python3 -m unittest discover -s tests` with every test passing.
- [ ] Output of the forgemyspec gate for the bundle ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If a requirement conflicts with another (for example value[:4] versus never the full value), stop and record the resolution as an assumption.
- [ ] Stop and ask before adding any command or option beyond the six listed.
