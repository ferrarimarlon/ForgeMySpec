# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Build a Small Parser CLI
- Objective: Develop a command-line interface application that parses input according to specified rules.

## Non-Negotiable Guardrails
- The CLI must accept input from standard input or command-line arguments.
- The parser should handle errors gracefully and provide meaningful messages.
- The implementation should be lightweight and not depend on heavy external libraries.

## Decision Rules
- If the parser fails to handle basic inputs, redesign the grammar.
- If the CLI crashes on invalid input, add error handling.
- If dependencies are heavy, refactor to reduce them.

## Success Criteria
- The CLI accepts input and outputs the parsed result correctly.
- The parser identifies and reports syntax errors in the input.
- The CLI runs without crashes or unhandled exceptions.
- The parser processes inputs within reasonable time for small inputs.

## Assumptions
- The parser will handle simple structured text inputs.
- The CLI will run on a standard terminal supporting basic input/output.
- No specific parsing language or grammar was provided, so a generic parser will be implemented.

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
