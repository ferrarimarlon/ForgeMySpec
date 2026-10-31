# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: ForgeMySpec trust kernel
- Objective: Prove in Dafny the five decisions that trust in ForgeMySpec depends on: each obligation's color, each requirement's status, the guards' decision about an edit, the coverage of hypotheses and phrases, and whether an approval counts. The Python of the guards, the gate and the risk box uses only the translation of this kernel for these decisions.

## Non-Negotiable Guardrails
- The kernel is pure: no I/O, no state, no {:extern}.
- Each decision has an exact output for every input case, so that mutants and planted errors are caught.
- None of these four decisions is reimplemented in Python.

## Decision Rules
- If a property cannot be proven as written, stop and amend the contract with the user; never weaken the clause to make the proof pass.
- If a planted error survives, strengthen the contract or the tests with new approval; never delete the error.

## Success Criteria
- `forgemyspec gate forgemyspec-bundle/kernel` passes every stage, with 100% of valid mutants killed and every planted error rejected.
- Each obligation has a Dafny test with concrete values, including each rule's edge cases.

## Assumptions
- The input types (status, phase, gate state, path category) are produced by the Python glue, which is tested but not proven.
- Failure and surviving-mutant counts arrive as natural numbers already summed by the gate.
- Dafny strings (seq<char>) translated to Python need conversion in the glue; the conversion is covered by the boundary tests.

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
