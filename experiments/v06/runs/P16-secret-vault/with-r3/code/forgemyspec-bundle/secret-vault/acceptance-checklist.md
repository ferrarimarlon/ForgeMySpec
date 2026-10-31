# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python CLI (vault.py) that stores secrets in an encrypted file under ~/.vault/, with TTL expiry, lockout after wrong passwords, and an audit log that never contains values.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All boundary tests in tests/test_vault.py pass.
- [ ] The vault file contains no plaintext value and starts with a 16-byte salt.
- [ ] File modes are 600 for vault.enc and 700 for ~/.vault/.

## Required Evidence
- [ ] Output of `python3 -m unittest discover tests` with all tests passing.
- [ ] Gate report ending in RESULT PASS.

## Decision Rules Compliance
- [ ] Stop and ask the user if a requirement conflicts with another or cannot be tested.
- [ ] Any change to behavior outside the obligations is a spec amendment.
