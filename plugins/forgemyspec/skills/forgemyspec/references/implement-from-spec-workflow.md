# Implement from spec (handoff)

Once `spec.yaml` passes the lint and the contract is locked, implementation is **strictly spec-first** and
ends only when the deterministic gate passes.

## Order

1. `/forgemyspec`: `spec.yaml` with a `formal` section; run `lint --formal` and `package`.
2. `/forgemyspec-formalize`: `contract.dfy`, `tests.dfy` and `planted/`; run `lock --check`; the user runs `lock`.
3. `/forgemyspec-implement`: `impl.dfy`, `shell/`, `tests_py/`; run `gate` until every stage passes.
4. `/forgemyspec-amend`: whenever implementation shows the spec or contract is wrong. Minimal delta, approval, `unlock`/`lock` by the user.

## Evidence

The gate report is the primary evidence. Add whatever `required_evidence` asks for that it does not cover
(command output, examples), and walk `acceptance-checklist.md` before calling the work done.

## Memory

The bundle's `CLAUDE.md` gets **durable** decisions and pitfalls only. Dafny lessons that apply to every
bundle belong in `references/dafny-patterns.md`.

## Scope drift

Scope is enforced mechanically: every `must_include` phrase maps to an obligation, every obligation to a proof
or a test, the lock keeps the approved contract fixed, and the guards deny edits outside an approved bundle.
`evals/scope_drift_cases.yaml` holds seeds for manual review on top of that.
