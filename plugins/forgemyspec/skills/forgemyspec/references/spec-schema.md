# spec.yaml schema (reference)

Operational spec for ForgeMySpec. Lists are deduplicated when normalized in the Python compiler; inside Claude, preserve clear, non-redundant entries.

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
- `generator`: Provenance when compiled by tooling. Do NOT include `model`.
- `scope_contract`: `{ must_include: string[] }` — short enforceable phrases covering critical functional requirements, security/safety constraints, and non-negotiable behaviors. Do NOT add `must_not_include` — use `constraints` for exclusions.

Full detail matches the project README section “Structure of the Generated Spec”.
