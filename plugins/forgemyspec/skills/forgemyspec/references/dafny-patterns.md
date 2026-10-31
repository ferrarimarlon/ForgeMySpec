# Dafny patterns and pitfalls (Dafny 4.x)

Facts observed while building the harness. Each one cost a failed run, so they live here.

## How the harness calls Dafny

| Stage | Command (run in a scratch copy of the bundle) | Pass condition |
| --- | --- | --- |
| verify | `dafny verify contract.dfy impl.dfy tests.dfy` | exit 0 |
| test | `dafny test --no-verify --target py contract.dfy impl.dfy tests.dfy` | exit 0 |
| audit | `dafny audit contract.dfy impl.dfy tests.dfy` | output says `completed with 0 findings` |
| translate | `dafny translate py --no-verify --include-runtime --output .../core contract.dfy impl.dfy` | exit 0, `core-py/` exists |

Exit codes: `0` ok, `2` parse/resolution error **or a warning** (warnings fail by default), `3` a `{:test}`
failed, `4` verification failed.

## Pitfalls

- **Included files are not verified.** `dafny verify tests.dfy` skips the bodies reached only through
  `include "impl.dfy"`, so a wrong implementation "verifies". Always pass every file explicitly.
- **`dafny audit` exits 0 even with findings.** Read the findings count.
- **A `match` case without braces runs to the end of the block.** In a loop body,
  `case A => x := 1; i := i + 1;` puts `i := i + 1` inside the last case only. Wrap the `match` in
  braces: `match t { case A => ... case B => ... }`. The verifier reports it as a termination failure.
- **`requires` is not checked at runtime in translated code.** The Python shell must check the core's
  preconditions itself, as a `kind: boundary` obligation with a test.
- **`expect` is an assumption to the verifier.** Code after `expect P` may use `P` without proof.
  The harness allows it only in `tests.dfy`.
- **Spec functions need bodies in the contract.** A bodiless `function`/`predicate` in the abstract
  module is filled in by `impl.dfy`, which then defines its own specification (`Valid(x) = true`).
- **Bodiless compiled methods in impl** are caught by `audit` and fail `verify` with a warning.
- **Contract clauses interlock.** Removing one `ensures` can break proofs elsewhere (a loop invariant
  that relied on it). That is useful: it shows which clauses carry weight.

## Translated Python API

For `module BudgetImpl refines BudgetCore` translated into `generated/core-py/`:

```python
import _dafny, BudgetImpl
BudgetImpl.default__.ApplyDeposit(10, 5)             # module-level methods live on default__
BudgetImpl.Tx_Deposit(10)                            # datatype constructor: <Type>_<Ctor>
txs = _dafny.SeqWithoutIsStrInference([...])         # Dafny seq from a Python list
final, rejected = BudgetImpl.default__.ApplyAll(0, txs)   # multiple outs return a tuple
outcome.is_Rejected, outcome.balance                 # discriminators and fields
```

Datatypes declared in the abstract contract module are emitted into the refining module's file.

## Writing contracts that kill mutants

- State outputs exactly (`r == Applied(b + a)`) instead of loosely (`r.balance >= b`).
- Cover each branch boundary: `<` vs `<=` survives unless some clause or test pins the equal case.
- Pin counters and accumulators (a count of rejections, a sum) with an `ensures`, or a mutant that
  corrupts them survives.
- Loop invariants in `impl.dfy` also kill mutants, but they are not part of the approved contract.
  The gate's mutation stage measures contract plus tests plus your proof, together.
