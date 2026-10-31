# spec.yaml schema (reference)

Operational spec for ForgeMySpec, written by Claude in the session and checked by `python3 -m forgemyspec lint`.
Keep entries clear and non-redundant: the linter warns on duplicates.

## Top level

| Field | Type | Notes |
| --- | --- | --- |
| `version` | string | e.g. `0.1`; a scope change bumps it |
| `title` | string | non-empty |
| `objective` | string | non-empty |
| `execution_mode` | string | always `critical` |
| `context` | object | see below |
| `constraints` | string[] | hard limits, including what stays out of scope |
| `success_criteria` | string[] | definition of done |
| `hypotheses` | object[] | `id`, `description`, `confidence` (0–1); affirmative and testable |
| `required_evidence` | string[] | proof required at delivery (observable outputs) |
| `actions` | object[] | see below |
| `decision_rules` | string[] | when to stop, escalate or choose |
| `metadata` | object | at least `source_prompt` |
| `formal` | object | required by the gate (`lint --formal`, `lock`, `approve`, `gate`); see below |
| `scope` | object | spec-only bundles (and shells outside the bundle); see below |

## `context`

- `system` (string, required): environment and repository framing.
- `assumptions` (string[]): explicit premises. The risk box lists them as trust placed in the user.

## `actions[]`

- unique `id`, `description`, `type` (`analyze`, `design`, `implement`, `validate`, `review`),
  `requires_confirmation` (boolean), `supports` (ids of the hypotheses the action advances).

## `metadata`

- `source_prompt`: the original request.
- `generator`: provenance, e.g. `claude-code-session`. Do not include `model`.
- `scope_contract.must_include`: short, exact phrases for every non-negotiable requirement. Each one becomes a line of the risk box.

## `formal`

Maps every requirement to something a machine checks: a Dafny proof obligation or a named Python test.

```yaml
formal:
  module: BudgetCore                    # name of the abstract module in contract.dfy
  obligations:
    - id: overdraft_rejected            # [a-z][a-z0-9_]*, unique; used in // @obligation and // @target tags
      kind: dafny                       # dafny | boundary
      statement: "ApplyWithdraw with amount > balance returns Rejected(balance, Overdraft)."
      hypotheses: [h2]                  # existing hypothesis ids
      must_include: ["overdraft rejected"]   # exact phrases from metadata.scope_contract.must_include
    - id: malformed_line
      kind: boundary
      statement: "A malformed ledger line exits 2 and names its line number."
      hypotheses: [h4]
      must_include: ["malformed line reported with line number"]
      test: "test_cli.CliTests.test_malformed_line_reports_line_number"   # unittest id
```

Coverage rules (LINT-FORMAL-*, decided by the proven kernel): every hypothesis and every `must_include` phrase
is covered by at least one obligation. Phrases must match exactly; paraphrases are rejected. A `boundary`
obligation needs a `test`. Each `dafny` obligation needs a `// @obligation <id>` tag above a clause or member of
`contract.dfy` and above a `{:test}` method of `tests.dfy` (LINT-DFY-005/006). Each planted error needs
`// @target <id>` (LINT-DFY-012/013).

## `scope`

```yaml
scope:
  paths: ["src/**", "tests/**"]   # paths outside the bundle it covers (the guards allow them once the bundle is approved)
  tests: tests                     # unittest folder with the boundary obligations' tests
  pythonpath: [src]                # extra PYTHONPATH entries for those tests
  verify_command: "npm test"       # extra command that must exit 0
```

A bundle without a Dafny contract is **spec-only**: it is approved with `approve` (writes `spec.lock`), and its
gate is the lint, coverage, the spec lock, the tests in `scope.tests` and `verify_command`.

## Formal bundle layout

```
<bundle>/
  spec.yaml          source of truth
  contract.dfy       abstract module: datatypes, spec functions (with bodies), bodiless methods + clauses
  tests.dfy          {:test} methods with concrete examples, tagged per obligation
  planted/*.dfy      plausible wrong implementations, each with // @target; all must be rejected
  contract.lock      hashes of contract.dfy, tests.dfy, planted/ and formal, plus the spec version (only the user writes it)
  impl.dfy           module refining the contract; every method has a body
  shell/             hand-written Python I/O over the translated core
  tests_py/          unittest boundary tests
  generated/core-py/ written by the gate (dafny translate py); never edited by hand
```
