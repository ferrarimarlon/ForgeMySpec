# Implement from spec (handoff)

After `spec.yaml` is linted and the contract is locked, implementation is **strictly spec-first** and
ends only when the deterministic gate passes.

## Order

1. `/forgemyspec`: `spec.yaml` with a `formal` section. Run `lint --formal` and `package`.
2. `/forgemyspec-formalize`: `contract.dfy` + `tests.dfy`. Run `lock --check`, get the user's approval, then `lock`.
3. `/forgemyspec-implement`: `impl.dfy`, `shell/`, `tests_py/`, then `gate` until every stage passes.
4. `/forgemyspec-amend`: whenever implementation shows the spec or contract is wrong. Change the minimal delta, get approval, and relock if the contract changed.

## Evidence

The gate report is the primary evidence. Add any `required_evidence` it does not cover (command
output, examples), then walk `acceptance-checklist.md` before claiming done.

## Memory

Update the bundle's `CLAUDE.md` with **durable** decisions and pitfalls only. Dafny lessons that apply
to every bundle belong in `references/dafny-patterns.md`.

## Scope drift

Scope is enforced mechanically: every `must_include` phrase maps to an obligation, every obligation to
a proof or a test, and the lock keeps the approved contract fixed. `evals/scope_drift_cases.yaml` holds
seeds for manual review on top of that.
