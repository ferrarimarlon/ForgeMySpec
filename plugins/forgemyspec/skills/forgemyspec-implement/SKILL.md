---
name: forgemyspec-implement
description: Implements a ForgeMySpec bundle whose Dafny contract is approved and locked. Writes impl.dfy (a module refining the contract), the thin Python I/O shell and its boundary tests, then runs the deterministic gate (verify, test, audit, translate to Python, boundary tests, mutation) until every stage passes. Use when spec.yaml, contract.dfy, tests.dfy and contract.lock exist.
---

# ForgeMySpec: implement against the locked contract

## Preconditions

- `<bundle>/spec.yaml`, `contract.dfy`, `tests.dfy` and `contract.lock` exist.
- The lock is current: `contract.dfy`, `tests.dfy` and the `formal` section are exactly what the user approved.

If any of them is missing or the contract looks wrong, stop. Use `/forgemyspec-formalize`
or `/forgemyspec-amend`. **Never edit `contract.dfy`, `tests.dfy` or `formal` here.** The gate
detects it, and weakening the contract to make code verify defeats the whole harness.

## 1. Write `impl.dfy`

```dafny
include "contract.dfy"
module <ImplModule> refines <formal.module> {
  method DoThing(x: int) returns (r: Result)
  {
    ...
  }
}
```

- Restate each method signature exactly and give it a body. The contract clauses are inherited.
- Loop invariants, `assert`s and helper lemmas are yours to add. They are proof, not cheating.
- Banned: `assume`, `expect`, `{:axiom}`, `{:verify false}`, `{:extern}`, `{:only}`, `decreases *`.
- Iterate quickly with Dafny directly, passing **all** files, because Dafny does not verify included files:

```bash
dafny verify <bundle>/contract.dfy <bundle>/impl.dfy <bundle>/tests.dfy
```

See `../forgemyspec/references/dafny-patterns.md` for pitfalls (match-case bodies, termination, `nat`).

## 2. Write the Python shell and boundary tests

- `<bundle>/shell/` holds hand-written I/O only: parsing, file and network access, printing, and
  **checks of the core's `requires`**, because translated Python does not check preconditions.
  The core's logic is never re-implemented in Python.
- The gate translates the core into `<bundle>/generated/core-py/` and puts it on `PYTHONPATH`, so the
  shell imports it directly (`import <ImplModule>`, `import _dafny`). Never edit `generated/`.
- `<bundle>/tests_py/` holds unittest tests. Every `kind: boundary` obligation names one of them
  (`test_x.Class.test_method`), and that test must exist and pass.

## 3. Run the gate

```bash
PYTHONPATH=src python3 -m forgemyspec gate <bundle>
```

Stages: spec-lint, obligation-coverage, dafny-lint, contract-lock, toolchain, verify, test, audit,
translate, python-boundary-tests, mutation. Any stage that is not PASS fails the gate, and later stages
report BLOCKED.

When **mutation** fails, a mutant of `impl.dfy` survived: the contract and tests accept wrong code.
- If the surviving behavior matters, the contract or tests are too weak. Go to `/forgemyspec-amend`
  and get re-approval. Do not lower `mutation_min_kill_rate`.
- If the mutant is truly equivalent (same behavior), mark the line with
  `// @equivalent-mutant: <reason>`. The gate lists every suppression in its report.

## 4. Report

Paste the full gate report as evidence, walk `acceptance-checklist.md` honestly, and list residual
risks. The biggest one is always the same: the contract may not say what the user meant. The
user's approval of the contract is the control for that.
