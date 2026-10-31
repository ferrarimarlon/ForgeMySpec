# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (password_checker.py) that checks passwords against a configurable policy, reports every failed rule, computes Shannon entropy, generates compliant random passwords, and validates policy files.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] check reports every failed rule in one run, not only the first.
- [ ] check prints the Shannon entropy in bits and exits 0 when compliant, 1 when not.
- [ ] generate outputs passwords that pass check under the same policy.
- [ ] validate-policy accepts a valid policy.json and rejects an invalid one with a message naming the problem.

## Required Evidence
- [ ] unittest run of tests/ passing, including each boundary obligation test
- [ ] Command output of check, generate and validate-policy against a sample policy.json

## Decision Rules Compliance
- [ ] If the policy is unsatisfiable (e.g. min_length smaller than the number of required classes), validate-policy rejects it.
- [ ] Ask the user before adding any rule or dependency beyond this spec.
