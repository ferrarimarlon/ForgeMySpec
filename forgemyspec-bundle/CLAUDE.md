# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Console Calculator with Basic Operations
- Objective: Create a console-based calculator that accepts user input and performs basic arithmetic operations.

## Non-Negotiable Guardrails
- The application must operate in a console environment.
- The application must support addition, subtraction, multiplication, and division.
- The application must validate user input before performing calculations.
- The application must handle division by zero safely and report the condition to the user.
- The implementation must avoid unsafe execution of user input as code.
- The scope is limited to basic arithmetic operations only.

## Decision Rules
- If the user input format is not otherwise specified, use an interactive prompt sequence for first number, operator, and second number.
- If a numeric input cannot be parsed, display a clear error message and do not perform a calculation.
- If the operator is not one of +, -, *, /, display a clear error message and do not perform a calculation.
- If division by zero is requested, display a clear error message and do not crash.
- If implementation language is unspecified, choose a language suitable for a simple console application and provide runnable code.

## Success Criteria
- A user can enter two numeric values and a supported operator in the console and receive the correct result.
- The calculator returns correct results for addition, subtraction, multiplication, and division in test cases.
- Invalid numeric input or unsupported operators produce a clear error message in the console.
- Division by zero produces a clear, safe error message without crashing the application.
- Evidence includes runnable console interaction examples or tests demonstrating all supported operations and error handling.

## Assumptions
- Basic operations means addition, subtraction, multiplication, and division.
- The calculator will run in an interactive console session.
- Users will enter two numeric operands and one operator per calculation.
- Division behavior will include explicit handling for division by zero.
- No persistence, networking, or graphical interface is required.

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
