# spec.yaml schema (reference)

Operational spec for ForgeMySpec, authored by Claude in the session and checked by `python3 -m forgemyspec lint`. Keep entries clear and non-redundant: the linter warns on duplicates.

## Top-level

| Field | Type | Notes |
| --- | --- | --- |
| `version` | string | e.g. `0.1` |
| `title` | string | Non-empty |
| `objective` | string | Non-empty |
| `execution_mode` | string | Always `critical` — treat every spec as a high-stakes contract |
| `context` | object | See below |
| `constraints` | string[] | Hard limits |
| `success_criteria` | string[] | Definition of done |
| `hypotheses` | object[] | `id`, `description`, `confidence` (0–1). Must be affirmative and testable — state what will work, never what will not be built |
| `required_evidence` | string[] | Proof required at delivery |
| `actions` | object[] | See below |
| `decision_rules` | string[] | Escalation / choice rules |
| `metadata` | object | At least `source_prompt` when policy requires it |
| `formal` | object | Required by the Dafny gate (`lint --formal`, `lock`, `gate`). See below |

## `context`

- `system` (string, required): Environment/repo framing.
- `assumptions` (string[]): Explicit premises.

## `actions[]`

- `id` (string): Unique among actions.
- `description` (string)
- `type` (string): Often `analyze`, `design`, `implement`, `validate`, `review` if policy-limited.
- `requires_confirmation` (boolean)
- `supports` (string[]): Hypothesis ids this action supports or depends on; must exist in `hypotheses`.

## `metadata`

Common keys:

- `source_prompt`: Original user requirement.
- `generator`: Provenance, for example `claude-code-session`. Do NOT include `model`.
- `scope_contract`: `{ must_include: string[] }` — short enforceable phrases covering critical functional requirements, security/safety constraints, and non-negotiable behaviors. Do NOT add `must_not_include` — use `constraints` for exclusions.

## `formal`

Maps every requirement to something a machine checks: a Dafny proof obligation, or a named Python test.

```yaml
formal:
  module: BudgetCore                  # name of the abstract module in contract.dfy
  obligations:
    - id: overdraft_rejected          # [a-z][a-z0-9_]*, unique; used in `// @obligation` tags
      kind: dafny                     # dafny | boundary
      statement: "ApplyWithdraw with amount > balance returns Rejected(balance, Overdraft)."
      hypotheses: [h2]                # existing hypothesis ids
      must_include: ["overdraft rejected"]   # exact phrases from metadata.scope_contract.must_include
    - id: malformed_line
      kind: boundary
      statement: "A malformed ledger line exits 2 and names its line number."
      hypotheses: [h4]
      must_include: ["malformed line reported with line number"]
      test: "test_cli.CliTests.test_malformed_line_reports_line_number"   # unittest id under tests_py/
```

Coverage rules (LINT-FORMAL-*): every hypothesis and every `must_include` phrase is covered by at least
one obligation. Phrases must match exactly, so paraphrases are rejected. A `boundary` obligation needs a `test`.
Each `dafny` obligation needs a `// @obligation <id>` tag above a clause or member in `contract.dfy` and
above a `{:test}` method in `tests.dfy` (LINT-DFY-005/006).

## Bundle layout

```
<bundle>/
  spec.yaml          source of truth
  contract.dfy       abstract module: datatypes, spec functions (with bodies), bodiless methods + clauses
  tests.dfy          {:test} methods with concrete examples, tagged per obligation
  contract.lock      hashes of contract.dfy, tests.dfy and `formal`, plus the spec version
  impl.dfy           module refining the contract; every method has a body
  shell/             hand-written Python I/O over the translated core
  tests_py/          unittest boundary tests
  generated/core-py/ written by the gate (dafny translate py); never edited by hand
```

