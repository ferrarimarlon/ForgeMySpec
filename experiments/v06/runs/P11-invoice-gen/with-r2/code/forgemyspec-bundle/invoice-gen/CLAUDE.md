# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Invoice generator CLI
- Objective: A single-file, stdlib-only Python CLI (invoice_gen.py) that reads an invoice JSON, validates it reporting all errors at once, computes line totals, subtotal, discount, tax and grand total with correct money rounding, and prints a formatted text invoice or exports JSON.

## Non-Negotiable Guardrails
- Python standard library only; one file invoice_gen.py.
- No floating point arithmetic for money.
- No PDF output, no network, no persistence, no multi-currency or per-item tax rates.

## Decision Rules
- If the discount or tax semantics in the assumptions are wrong, stop and amend the spec.
- If a rule cannot be tested at the boundary, escalate instead of weakening it.

## Success Criteria
- An invalid invoice prints every validation error at once and exits 2.
- Totals for a valid invoice match hand-computed values including half-cent rounding cases.
- Text and JSON outputs show the same computed amounts.

## Assumptions
- Discount is an object {type: percent|fixed, value: number}; percent is 0-100, fixed is >= 0 and <= subtotal.
- Tax is applied to the discounted subtotal (subtotal - discount); tax_rate is a percentage (e.g. 8.25).
- Money uses decimal.Decimal with ROUND_HALF_UP to 2 places: each line total is rounded, then subtotal is the sum of rounded line totals, discount and tax are rounded once each.
- Input numbers are parsed from JSON as Decimal (no float); quantity may be fractional but must be > 0, unit_price >= 0.
- Customer requires a non-empty name; other customer fields (email, address) are optional strings.
- Single currency, formatted with two decimals and no currency conversion.
- CLI: invoice_gen.py INPUT.json [--format text|json] [--output FILE]; exit 0 ok, 2 invalid input or validation errors.

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
