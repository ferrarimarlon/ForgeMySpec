# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Password policy checker CLI
- Objective: Single-file stdlib-only Python CLI (password_checker.py) that checks a password against a configurable policy, reports every failed rule, computes Shannon entropy, generates compliant random passwords, and validates policy files.

## Non-Negotiable Guardrails
- Single file password_checker.py, standard library only (no third-party imports).
- No network access and no logging or printing of passwords except generated ones on stdout.
- Generation uses the secrets module, never random.
- Not building a GUI, a breach-database lookup, or strength scoring beyond Shannon entropy.

## Decision Rules
- If a policy is unsatisfiable (length below required class count), validate-policy and generate must fail with exit 2 rather than emit a non-compliant password.
- Stop and ask if a requirement needs a third-party package.

## Success Criteria
- check reports every failed rule in one run, not only the first.
- generate always yields passwords that pass check under the same policy.
- validate-policy rejects malformed policies with clear messages and exit code 2.

## Assumptions
- Policy JSON keys: min_length (int >= 1), require_uppercase, require_lowercase, require_digits, require_symbols (bool), forbidden_passwords (list of strings). Missing keys take defaults (min_length 8, all requires false, forbidden list empty plus built-in common list).
- Symbols means any printable non-alphanumeric ASCII character (string.punctuation); non-ASCII letters count as neither uppercase nor lowercase unless str.isupper/islower says so.
- Forbidden-password matching is case-insensitive and exact against the whole password; a small built-in common-password list is always applied in addition to the policy list.
- Shannon entropy is computed from the character frequencies of the password: H = -sum(p*log2 p) per character, reported as total bits = len * H (0.0 for the empty password).
- Exit codes: 0 success/compliant, 1 password violates policy, 2 usage or invalid policy/file error.
- The password is read from the positional argument or from stdin with --stdin, to avoid shell history exposure.

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
