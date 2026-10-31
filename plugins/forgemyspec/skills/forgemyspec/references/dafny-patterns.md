# Dafny patterns and pitfalls (Dafny 4.x)

Facts observed while building the harness. Each one cost a failed run, so they live here.

## How the harness calls Dafny

| Stage | Command (run in a scratch copy of the bundle) | Passes when |
| --- | --- | --- |
| verify | `dafny verify contract.dfy impl.dfy tests.dfy` | exit 0 |
| test | `dafny test --no-verify --target py contract.dfy impl.dfy tests.dfy` | exit 0 |
| audit | `dafny audit contract.dfy impl.dfy tests.dfy` | output says `completed with 0 findings` |
| translate | `dafny translate py --no-verify --include-runtime --output .../core contract.dfy impl.dfy` | exit 0 and `core-py/` exists |
| planted errors | the same verify and test, with each `planted/*.dfy` in place of `impl.dfy` | every error rejected (exit 4 or 3) |

Exit codes: `0` ok, `2` parse/resolution error **or a warning** (warnings fail by default), `3` a `{:test}`
failed, `4` verification failed.

## Pitfalls

- **Included files are not verified.** `dafny verify tests.dfy` skips bodies reached only through `include "impl.dfy"`, and a wrong implementation "verifies". Always pass every file.
- **`dafny audit` exits 0 even with findings.** Read the count.
- **A `match` case without braces runs to the end of the block.** In a loop body, `case A => x := 1; i := i + 1;` puts `i := i + 1` in the last case only. Use `match t { case A => ... case B => ... }`. The verifier reports it as a termination failure.
- **`==>` split across lines** with ambiguous indentation raises a warning (which fails). One implication per line.
- **`requires` is not checked at runtime in translated code.** The Python shell checks the core's preconditions, as a boundary obligation with a test.
- **`expect` is an assumption to the verifier.** Code after `expect P` may use `P` without proof. The harness allows `expect` only in `tests.dfy`.
- **Spec functions need bodies in the contract.** A bodiless `function`/`predicate` in the abstract module is filled in by `impl.dfy`, which then defines its own specification (`Valid(x) = true`).
- **Bodiless compiled methods in impl** are caught by the audit and fail verification with a warning.
- **Contract clauses interlock.** Removing one `ensures` can break proofs elsewhere (a loop invariant that relied on it). That is useful: it shows which clauses carry weight.
- **Translation to Python is deterministic.** Two translations of the same code give identical files, which lets CI check `src/forgemyspec/_kernel/`.

## Translated Python API

For `module BudgetImpl refines BudgetCore` translated into `generated/core-py/`:

```python
import _dafny, BudgetImpl
BudgetImpl.default__.ApplyDeposit(10, 5)                 # module-level methods live on default__
BudgetImpl.Tx_Deposit(10)                                # datatype constructor: <Type>_<Ctor>
txs = _dafny.SeqWithoutIsStrInference([...])             # Dafny seq from a Python list
final, rejected = BudgetImpl.default__.ApplyAll(0, txs)  # multiple outs return a tuple
outcome.is_Rejected, outcome.balance                     # discriminators and fields
_dafny.Seq("text"); "".join(seq)                         # Dafny string (seq<char>) there and back
```

Datatypes declared in the abstract contract module are emitted into the refining module's file.

## Contracts that kill mutants and planted errors

- State outputs exactly (`r == Applied(b + a)`), not loosely (`r.balance >= b`).
- Cover each branch boundary: `<` vs `<=` survives unless some clause or test pins the equal case.
- Pin counters and accumulators (a count of rejections, a sum) with an `ensures`, or a mutant that corrupts them survives.
- Write planted errors from the mistakes you yourself could make in that code.
