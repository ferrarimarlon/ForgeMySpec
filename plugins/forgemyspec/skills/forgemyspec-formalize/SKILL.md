---
name: forgemyspec-formalize
description: Turns an approved ForgeMySpec spec.yaml into a Dafny contract (contract.dfy, an abstract module) and Dafny tests (tests.dfy), gets the user's approval, and locks them with contract.lock so the implementation phase cannot weaken them. Use after /forgemyspec and before /forgemyspec-implement, or whenever the formal obligations change.
---

# ForgeMySpec: formalize the contract

The contract is the one artifact the user must review, so keep it short, readable, and exactly as
strong as the obligations say. Read `../forgemyspec/references/dafny-patterns.md` before writing Dafny.

## Preconditions

- `<bundle>/spec.yaml` exists and `PYTHONPATH=src python3 -m forgemyspec lint <bundle>/spec.yaml --formal` passes.

## 1. Write `contract.dfy`

```dafny
abstract module <formal.module> {
  // datatypes, and spec functions/predicates WITH bodies (they define the meaning)

  method DoThing(x: int) returns (r: Result)
    requires ...
    // @obligation <id>
    ensures ...
}
```

- One `abstract module` named exactly `formal.module`.
- Methods have **no body** and at least one `ensures`. Functions and predicates **must have a body**, or the implementation would get to define the specification.
- Put `// @obligation <id>[, <id>]` directly above the clause or member that states each `kind: dafny` obligation.
- State results exactly (`r == Applied(b + a)`), not loosely (`r.balance > b`). Loose clauses let wrong code verify, and the mutation stage will catch it later.
- Banned: `assume`, `expect`, `{:axiom}`, `{:verify false}`, `{:extern}`, `{:only}`, `decreases *`, `requires false`, `ensures true`.

## 2. Write `tests.dfy`

```dafny
include "impl.dfy"
module <Name>Tests {
  import opened <ImplModule>
  // @obligation <id>
  method {:test} SomeCase() { var r := DoThing(3); expect r == ...; }
}
```

- At least one `{:test}` method tagged for every `kind: dafny` obligation, with concrete values. Examples are what a human checks fastest.
- Include boundary values (zero, equal-to-limit, one past the limit, empty sequences).
- Choose the implementation module name now (for example `<Module>Impl`). `impl.dfy` must use it.

## 3. Check before asking

```bash
dafny verify <bundle>/contract.dfy                              # the contract is well-formed
PYTHONPATH=src python3 -m forgemyspec lock <bundle> --check     # coverage + Dafny lint, writes nothing
```

`impl.dfy` does not exist yet, so `tests.dfy` cannot be verified until `/forgemyspec-implement`.

## 4. Get approval, then lock

Show the user `contract.dfy` and `tests.dfy` next to the obligations table, and say in one line what
each clause guarantees. Ask explicitly: **"Approve this contract?"** Only after a clear yes:

```bash
PYTHONPATH=src python3 -m forgemyspec lock <bundle>
```

`lock` refuses if spec-lint, obligation coverage or the Dafny lint fail. It records SHA-256 hashes of
`contract.dfy`, `tests.dfy` and the spec's `formal` section, plus the spec version. Any later edit to
those makes the gate fail until the user re-approves and `lock` runs again.

If the semantics are ambiguous, stop and ask before locking. Never lock on your own judgment.
