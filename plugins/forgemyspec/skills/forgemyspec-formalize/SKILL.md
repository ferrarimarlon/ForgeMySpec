---
name: forgemyspec-formalize
description: Turns an approved ForgeMySpec spec.yaml into a Dafny contract (contract.dfy, an abstract module), Dafny tests (tests.dfy) and planted errors (planted/), shows them to the user and waits for the user to lock them with `lock`, so the implementation cannot weaken them. Use after /forgemyspec and before /forgemyspec-implement, or whenever the formal obligations change.
---

# ForgeMySpec: formalize the contract

The contract is the one artifact the user must review, so keep it short, readable, and exactly as strong as
the obligations say. Read `../forgemyspec/references/dafny-patterns.md` before writing Dafny.

## Precondition

- `<bundle>/spec.yaml` exists and `lint <bundle>/spec.yaml --formal` passes.

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
- Methods have **no body** and at least one `ensures`. Functions and predicates **must have a body**, or the implementation would get to define its own specification.
- Put `// @obligation <id>[, <id>]` directly above the clause or member that states each `kind: dafny` obligation.
- State results exactly (`r == Applied(b + a)`), not loosely (`r.balance > b`). Loose clauses let wrong code verify, and mutation and planted errors catch that later.
- One implication per line: Dafny warns (and the warning fails) when `==>` breaks across lines with ambiguous indentation.
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

- At least one tagged `{:test}` method for every `kind: dafny` obligation, with concrete values. Examples are what a human checks fastest.
- Include edge values (zero, equal to the limit, one past the limit, empty sequences).
- Choose the implementation module name now (for example `<Module>Impl`); `impl.dfy` will use it.

## 3. Write the planted errors (`planted/*.dfy`)

At least 3 (policy `min_planted_errors`). Each one is a **whole `impl.dfy` that is wrong in a plausible way**:
the mistake an LLM would make (off-by-one, a forgotten branch, a counter that never increments, a cache
accepted without checking). Each file starts with:

```dafny
// @target <id-of-the-obligation-that-should-catch-this-error>
// Planted error: <the mistake, in one line>
```

The gate requires the contract and the tests to reject all of them. A planted error that does not compile measures nothing and fails the stage.

## 4. Check before showing

```bash
dafny verify <bundle>/contract.dfy                                   # the contract is well-formed
PYTHONPATH=src python3 -m forgemyspec lock <bundle> --check           # coverage + Dafny lint, writes nothing
```

`impl.dfy` does not exist yet, so `tests.dfy` can only be verified in `/forgemyspec-implement`.

## 5. Ask for approval

Show the user `contract.dfy`, `tests.dfy` and the list of planted errors next to the obligations table, and
say in one line what each clause guarantees. Ask explicitly: **"Approve this contract?"** Approval is the
user running, **in their own terminal**:

```bash
PYTHONPATH=src python3 -m forgemyspec lock <bundle>
```

`lock` refuses when the lint, coverage or the Dafny lint fail. It records SHA-256 hashes of `contract.dfy`,
`tests.dfy`, `planted/` and the `formal` section, plus the spec version. Any later change to those makes the
gate fail until the user approves again.

If the semantics are ambiguous, stop and ask first. Never try to run `lock` yourself: the guards refuse it.
