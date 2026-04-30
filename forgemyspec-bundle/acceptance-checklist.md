# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Create a console-based calculator that accepts user input and performs basic arithmetic operations.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A user can enter two numeric values and a supported operator in the console and receive the correct result.
- [ ] The calculator returns correct results for addition, subtraction, multiplication, and division in test cases.
- [ ] Invalid numeric input or unsupported operators produce a clear error message in the console.
- [ ] Division by zero produces a clear, safe error message without crashing the application.
- [ ] Evidence includes runnable console interaction examples or tests demonstrating all supported operations and error handling.

## Required Evidence
- [ ] Source code for the console calculator.
- [ ] Demonstration output or tests showing correct addition, subtraction, multiplication, and division results.
- [ ] Demonstration output or tests showing handling of invalid numeric input.
- [ ] Demonstration output or tests showing handling of unsupported operators.
- [ ] Demonstration output or tests showing safe handling of division by zero.

## Decision Rules Compliance
- [ ] If the user input format is not otherwise specified, use an interactive prompt sequence for first number, operator, and second number.
- [ ] If a numeric input cannot be parsed, display a clear error message and do not perform a calculation.
- [ ] If the operator is not one of +, -, *, /, display a clear error message and do not perform a calculation.
- [ ] If division by zero is requested, display a clear error message and do not crash.
- [ ] If implementation language is unspecified, choose a language suitable for a simple console application and provide runnable code.
