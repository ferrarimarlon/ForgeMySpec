# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Invoice generator CLI
- Objective: A single-file stdlib-only Python CLI (invoice_gen.py) that reads an invoice JSON, validates it reporting all errors at once, computes totals with correct money rounding, and prints a text invoice or exports JSON.

## Non-Negotiable Guardrails
- Standard library only; one file invoice_gen.py.
- No binary floats in money arithmetic; use decimal.Decimal.
- No PDF, HTML, multi-currency, database or network features.

## Decision Rules
- If an input rule is ambiguous, stop and ask rather than guess.
- Anything beyond these obligations is a spec amendment.

## Success Criteria
- All validation errors of an invalid invoice are printed in one run.
- Totals match hand-computed values including half-cent cases.
- Text and JSON outputs both work from the CLI.

## Assumptions
- Input shape: customer {name (required), email/address optional}, items [{description, quantity, unit_price}], tax_rate, optional discount, optional invoice number and date.
- tax_rate is a percentage (8.25 means 8.25%), between 0 and 100.
- discount is an object {type: percent|fixed, value}; percent is 0-100, fixed is 0 up to the subtotal.
- Single currency, two decimals; rounding is half-up to the cent, applied to each line total, the discount and the tax.
- Tax is computed on the subtotal after discount.
- Exit codes: 0 success, 1 invalid invoice, 2 usage or unreadable/non-JSON file.

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
