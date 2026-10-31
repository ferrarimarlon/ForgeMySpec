# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Config validator CLI
- Objective: A single-file stdlib-only Python CLI, config_validator.py, that validates a JSON config file against a JSON schema file and reports all errors at once.

## Non-Negotiable Guardrails
- Standard library only; no third-party packages.
- Everything lives in the single file config_validator.py.
- No support for $ref, oneOf, anyOf, allOf, or array item schemas.
- Properties not named in the schema are ignored.

## Decision Rules
- If a schema keyword outside the listed subset is needed, stop and ask for a spec amendment.

## Success Criteria
- A valid config exits 0 and reports no errors.
- An invalid config lists every violation, one per line, and exits 1.

## Assumptions
- The schema dialect is a small JSON-Schema-like subset: a top-level object schema with properties, required, type, enum, minimum, maximum, minLength, maxLength, pattern.
- The CLI usage is: python3 config_validator.py <config.json> <schema.json>.
- Exit code 0 when valid, 1 when validation errors exist, 2 for usage, file or JSON parse problems.
- Booleans are not accepted as integer or number; integer accepts only ints (not floats).
- Regex patterns use re.search semantics, as in JSON Schema.
- Nested paths use dot notation (server.port); array items are not validated beyond the array type.

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
