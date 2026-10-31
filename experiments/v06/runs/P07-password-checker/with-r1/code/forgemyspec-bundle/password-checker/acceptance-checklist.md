# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib-only Python CLI (password_checker.py) that checks a password against a configurable policy, reports every failed rule, computes Shannon entropy, generates compliant random passwords, and validates policy files.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] check reports every failed rule in one run, not only the first.
- [ ] generate always yields passwords that pass check under the same policy.
- [ ] validate-policy rejects malformed policies with clear messages and exit code 2.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests passing.
- [ ] Command output of check on a password failing several rules listing each failed rule.
- [ ] Command output of generate followed by check on the result exiting 0.

## Decision Rules Compliance
- [ ] If a policy is unsatisfiable (length below required class count), validate-policy and generate must fail with exit 2 rather than emit a non-compliant password.
- [ ] Stop and ask if a requirement needs a third-party package.
