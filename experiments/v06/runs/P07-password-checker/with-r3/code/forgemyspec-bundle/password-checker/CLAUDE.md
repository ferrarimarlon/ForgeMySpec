# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Password policy checker CLI
- Objective: A single-file, stdlib-only Python CLI (password_checker.py) that checks passwords against a configurable policy, reports every failed rule, computes Shannon entropy, generates compliant random passwords, and validates policy files.

## Non-Negotiable Guardrails
- Single file password_checker.py; Python standard library only, no third-party packages.
- No network access, no password storage or logging.
- Not a strength estimator beyond Shannon entropy; no breach-database lookup.
- The password is never echoed in the output of check.

## Decision Rules
- If the policy is unsatisfiable (e.g. min_length smaller than the number of required classes), validate-policy rejects it.
- Ask the user before adding any rule or dependency beyond this spec.

## Success Criteria
- check reports every failed rule in one run, not only the first.
- check prints the Shannon entropy in bits and exits 0 when compliant, 1 when not.
- generate outputs passwords that pass check under the same policy.
- validate-policy accepts a valid policy.json and rejects an invalid one with a message naming the problem.

## Assumptions
- Policy fields: min_length (int >= 1), require_uppercase, require_lowercase, require_digits, require_symbols (booleans), forbidden_passwords (list of strings, compared case-insensitively).
- Symbols are ASCII punctuation characters (string.punctuation).
- Shannon entropy is the per-character empirical entropy H times the password length, in bits.
- The default policy path is policy.json in the current directory; --policy overrides it; with no file a built-in default policy applies.
- Exit codes: 0 success, 1 password fails policy, 2 invalid input or policy.
- Randomness comes from the secrets module.

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
