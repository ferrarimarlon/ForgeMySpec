# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (password_checker.py) with subcommands check, generate and validate-policy that evaluates passwords against a configurable policy loaded from policy.json, reports every failed rule, computes Shannon entropy in bits, and generates random passwords satisfying the policy.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] check reports every failed rule in one run, not only the first.
- [ ] A compliant password exits 0; a non-compliant one exits 1 and lists each failed rule.
- [ ] Every generated password passes check under the same policy.
- [ ] validate-policy accepts a well-formed policy and rejects malformed ones with a clear message and exit 2.

## Required Evidence
- [ ] unittest run output of tests/ showing all tests passing
- [ ] gate report ending in RESULT: PASS
- [ ] command output of check on a weak password listing several failed rules

## Decision Rules Compliance
- [ ] If a policy is unsatisfiable (for example min_length smaller than the number of required classes), validate-policy rejects it rather than guessing.
- [ ] If a requirement is ambiguous, ask the user; do not widen scope.
