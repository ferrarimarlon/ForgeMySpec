---
name: forgemyspec-implement
description: Implements a ForgeMySpec bundle whose Dafny contract the user has approved and locked. Writes impl.dfy (a module refining the contract), the Python I/O shell and its boundary tests, and runs the deterministic gate (verification, tests, audit, translation to Python, boundary tests, mutation, planted errors) until every stage passes. Use when spec.yaml, contract.dfy, tests.dfy, planted/ and contract.lock exist.
---

# ForgeMySpec: implement against the locked contract

## Preconditions

- `<bundle>/spec.yaml`, `contract.dfy`, `tests.dfy`, `planted/` and `contract.lock` exist.
- The lock matches: contract, tests, planted errors and the `formal` section are exactly what the user approved.

If something is missing or the contract looks wrong, stop and use `/forgemyspec-formalize` or
`/forgemyspec-amend`. **Never edit `contract.dfy`, `tests.dfy`, `planted/` or `formal` here.** The guards deny
the edit, and weakening the contract to make code verify defeats the whole harness.

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
- Loop invariants, `assert`s and helper lemmas are yours to add: they are proof, not cheating.
- Banned: `assume`, `expect`, `{:axiom}`, `{:verify false}`, `{:extern}`, `{:only}`, `decreases *`.
- Iterate quickly with Dafny, passing **all** files (Dafny does not verify included files):

```bash
dafny verify <bundle>/contract.dfy <bundle>/impl.dfy <bundle>/tests.dfy
```

See the pitfalls in `../forgemyspec/references/dafny-patterns.md`.

## 2. Write the Python shell and boundary tests

- `<bundle>/shell/` holds hand-written I/O only: parsing, files, network, printing and **checks of the core's
  `requires`**, because translated Python does not check preconditions. The logic is never rewritten in Python.
- The gate translates the core into `<bundle>/generated/core-py/` and puts it on `PYTHONPATH`; the shell imports
  it directly (`import <ImplModule>`, `import _dafny`). Never edit `generated/`.
- `<bundle>/tests_py/` holds unittest tests. Every `kind: boundary` obligation names one of them, and it must exist and pass.

## 3. Run the gate

```bash
PYTHONPATH=src python3 -m forgemyspec gate <bundle>
```

Stages: spec lint, coverage, Dafny lint, lock, toolchain, verification, Dafny tests, audit, translation,
boundary tests, mutation and planted errors. Any stage that does not pass fails the gate, and later stages
report BLOCKED. The Stop hook will not let you end the turn while an approved bundle has no current passing gate.

- **Mutation failed:** a mutant of `impl.dfy` survived; the contract and tests accept wrong code. If the behavior
  matters, the contract is weak: use `/forgemyspec-amend` and get new approval. Never lower `mutation_min_kill_rate`.
  If the mutant is truly equivalent, mark the line with `// @equivalent-mutant: <reason>`; the report lists every suppression.
- **A planted error survived:** a realistic mistake passes. The `@target` requirement shows as LEAKING in the box.
  Strengthen the contract or the tests with new approval; never delete the planted error.

## 4. Report

Paste the full gate report, walk `acceptance-checklist.md` honestly and list residual risks. The biggest one is
always the same: the contract may not say what the user meant. The user's approval of the contract is the
control for that, and the risk box reminds them on every prompt.
