# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Invoice generator CLI
- Objective: Single-file stdlib Python CLI (invoice_gen.py) that reads an invoice JSON, validates it reporting all errors at once, computes totals with correct money rounding, and prints a text invoice or exports JSON.

## Non-Negotiable Guardrails
- Single file invoice_gen.py, Python standard library only.
- No floating-point arithmetic for money.
- No network, no database, no PDF output, no multi-currency, no persistence.
- Validation never stops at the first error.

## Decision Rules
- If a rule is ambiguous (discount shape, tax base), stop and amend the spec instead of guessing.
- Stop when any test fails; do not weaken tests.

## Success Criteria
- A valid invoice prints a formatted text invoice and the same figures export as JSON.
- An invoice with several defects lists every defect in one run.
- Rounding cases such as 0.005 and 1.005 totals round half-up to the cent.

## Assumptions
- Money is computed with decimal.Decimal, rounded half-up to 2 places; floats are never used for money.
- tax_rate is a percentage (8.25 means 8.25%), between 0 and 100 inclusive.
- discount is optional: an object {type: percent|fixed, value: number}; percent is 0-100, fixed is >= 0 and at most the subtotal.
- Discount applies to the subtotal; tax is computed on the discounted subtotal.
- Each line total is rounded to cents first; subtotal is the sum of rounded line totals.
- quantity is a number > 0 (decimals allowed); unit_price is a number >= 0; customer is an object with a non-empty name.
- Currency is a single implicit currency with 2 decimals; no currency symbol logic beyond a plain amount format.
- CLI: invoice_gen.py INPUT.json [--format text|json]; default text; exit 0 ok, 1 invalid invoice, 2 unreadable file or bad JSON.

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
