# spec.yaml schema (reference)

Operational spec for ForgeMySpec. Lists are deduplicated when normalized in the Python compiler; inside Claude, preserve clear, non-redundant entries.

## Top-level

| Field | Type | Notes |
| --- | --- | --- |
| `version` | string | e.g. `0.1` |
| `title` | string | Non-empty |
| `objective` | string | Non-empty |
| `execution_mode` | string | e.g. `advisory`, `step_by_step` |
| `context` | object | See below |
| `constraints` | string[] | Hard limits |
| `success_criteria` | string[] | Definition of done |
| `hypotheses` | object[] | `id`, `description`, `confidence` (0–1) |
| `required_evidence` | string[] | Proof required at delivery |
| `actions` | object[] | See below |
| `decision_rules` | string[] | Escalation / choice rules |
| `metadata` | object | At least `source_prompt` when policy requires it |

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
- `generator`, `model`: Provenance when compiled by tooling.
- `scope_contract`: `{ must_include: string[] }` when scope is explicit. List short phrases that must be present in the implementation. Do NOT add a `must_not_include` field — use `constraints` to document what will not be built.

Full detail matches the project README section “Structure of the Generated Spec”.
