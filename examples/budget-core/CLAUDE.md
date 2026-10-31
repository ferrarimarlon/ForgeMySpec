# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Budget ledger core with a verified balance contract
- Objective: Replay a ledger of deposits and withdrawals from an opening balance, rejecting overdrafts and non-positive amounts, with the arithmetic proven in Dafny and exposed to users through a small Python command-line shell.

## Non-Negotiable Guardrails
- Ledger arithmetic exists only in the Dafny core; the Python shell parses, validates preconditions and prints.
- The shell refuses a negative opening balance before calling the core, because translated code does not check `requires`.
- Python shell uses the standard library only.

## Decision Rules
- If a contract clause turns out to be unprovable as written, stop and amend the spec and contract with user approval instead of weakening impl.dfy.
- If a mutant or a planted error survives, strengthen tests.dfy or the contract through re-approval, or justify an equivalent mutant in impl.dfy.

## Success Criteria
- `python3 -m forgemyspec gate examples/budget-core` exits 0 with every stage PASS.
- Replaying `deposit 10, withdraw 4, withdraw 7, deposit -1, deposit 2` from 0 prints `balance=8 rejected=2`.
- A malformed ledger line makes the CLI exit 2 and name the line number on stderr.

## Assumptions
- Amounts and balances are unbounded integers; the ledger file is small enough to read into memory.
- A rejected transaction leaves the balance unchanged and is counted, and replay continues.
- The ledger format is one `deposit <int>` or `withdraw <int>` per line; blank lines and `#` comments are ignored.

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
