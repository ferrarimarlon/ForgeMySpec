# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Config validator CLI
- Objective: A single-file, stdlib-only Python CLI (config_validator.py) that validates a JSON config file against a JSON schema file and reports every error at once.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- All code lives in the single file config_validator.py.
- Out of scope: $ref, oneOf/anyOf/allOf, array item schemas, format, additionalProperties, default values.

## Decision Rules
- If a schema keyword outside the listed subset is needed, stop and ask for a spec amendment.
- If a check cannot be tested at the boundary, stop and escalate.

## Success Criteria
- Running the CLI on an invalid config prints every violation, one per line, and exits 1.
- Running the CLI on a valid config exits 0.

## Assumptions
- Schema dialect is a JSON-Schema-like subset: top-level object schema with properties, required, type, enum, minimum, maximum, minLength, maxLength, pattern; nested objects use properties/required recursively.
- Regex patterns use Python re.search semantics (unanchored, as in JSON Schema).
- A boolean is not an integer or number; an integer-valued float such as 3.0 is accepted as number but not as integer.
- Exit codes: 0 valid, 1 validation errors, 2 usage or unreadable/invalid JSON input.
- Array items are type-checked only as arrays; no item schemas, minItems or maxItems.

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
