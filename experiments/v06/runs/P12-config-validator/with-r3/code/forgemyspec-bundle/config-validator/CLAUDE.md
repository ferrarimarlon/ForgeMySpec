# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Config validator CLI
- Objective: A single-file, stdlib-only Python CLI (config_validator.py) that validates a JSON config file against a JSON schema file and reports every violation at once, with nested fields addressed in dot notation.

## Non-Negotiable Guardrails
- Single file config_validator.py; Python standard library only, no third-party packages.
- No support for $ref, oneOf/anyOf/allOf, additionalProperties, array items, format or schema-draft keywords; unknown keywords are ignored.
- Never stop at the first error; never raise a traceback for invalid configs.

## Decision Rules
- If a schema keyword outside the listed subset is needed, stop and amend the spec.
- If the gate fails, fix the implementation, never the approved spec.

## Success Criteria
- A config violating several rules yields one error line per violation in a single run.
- A valid config exits 0 and an invalid one exits 1.

## Assumptions
- The schema uses a JSON-Schema-style subset: top-level and nested objects use type, properties and required; leaf fields use type, enum, minimum, maximum, minLength, maxLength and pattern.
- CLI usage is python3 config_validator.py <schema.json> <config.json>; exit 0 when valid, 1 when validation errors exist, 2 for usage, unreadable file or malformed JSON.
- Patterns use re.search semantics (unanchored), like JSON Schema.
- Booleans are rejected as integer or number; integer accepts only int values, number accepts int and float.
- Properties present in the config but absent from the schema are allowed and ignored.
- A constraint keyword is checked only when the value has the matching type; a type mismatch yields one type error for that field and skips its other constraints.

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
