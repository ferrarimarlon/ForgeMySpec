# Implement from spec (handoff)

After `spec.yaml` and the bundle exist, implementation should be **strictly spec-first**.

## Entry

Use the generated `.claude/commands/implement-from-spec.md` or equivalent instructions. The agent should:

1. Read `spec.yaml` end-to-end.
2. Map `actions` to an ordered or phased plan (respecting dependencies implied by `supports` and hypotheses).
3. Implement only what traceability covers; expand scope only by updating the spec and assumptions.
4. Collect **required_evidence** (commands run, test output, screenshots if applicable).
5. Walk `acceptance-checklist.md` before claiming done.

## Memory

Update `CLAUDE.md` with **durable** project decisions (conventions, pitfalls). Do not store transient debug output there.

## Scope drift

Compare work against `metadata.scope_contract` and `evals/scope_drift_cases.yaml` when evaluating whether the implementation stayed on brief.
