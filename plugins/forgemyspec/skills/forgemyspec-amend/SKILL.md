---
name: forgemyspec-amend
description: Safely amends an existing ForgeMySpec spec.yaml in response to new information discovered during implementation (wrong assumption, tightened constraint, scope change). Proposes only the minimal delta, validates the result with lint, and shows a diff before writing. Never rewrites the whole spec without explicit user approval.
---

# ForgeMySpec Amend (safe spec iteration)

Use this skill when a `spec.yaml` already exists and needs to change — **not** to compile a spec from scratch (use `/forgemyspec` for that).

## When to apply

| Trigger | Scenario |
|---|---|
| Assumption proved wrong | A hypothesis failed; the spec's model of the system was incorrect |
| Constraint needs tightening | Implementation revealed an edge case not covered by existing constraints |
| Scope change | User adds, removes, or reprioritizes a requirement during implementation |
| Hypothesis confidence revised | Evidence changes the probability estimate |
| Major pivot | The objective itself changes (requires explicit user approval and version bump) |

## Principle

> **Amend the minimum needed. Never rewrite what is still true.**

The spec is a contract. Unnecessary rewrites erode trust in the history and break traceability. Propose only the fields that must change; preserve everything else verbatim.

---

## Workflow

### 1. Read the current spec

```bash
cat <path-to-spec.yaml>
```

Note the current `version`, all `hypotheses[].id` values, and `actions[].supports` links — these are the traceability backbone. Do not touch them unless the change explicitly requires it.

### 2. Understand the change request

Ask (or infer from context):

- **What new information arrived?** (test failure, user message, code discovery)
- **What was wrong or incomplete?** (which field, which item, which link)
- **What scenario applies?** Surgical edit / scope change / major pivot

If the scenario is a **major pivot** (objective changes), stop and confirm with the user before proceeding.

### 3. Identify the minimal delta

Produce a precise list of changes **before touching the file**:

```
DELTA
  hypotheses[2].confidence: 0.8 → 0.4   (evidence contradicted assumption)
  constraints: + "Must handle Unicode input up to 4-byte codepoints"
  success_criteria[1]: "Returns exit code 0" → "Returns exit code 0 and prints parsed result to stdout"
```

If any `hypothesis.id` is changing, also update every `action.supports` that references it.

### 4. Validate the proposed spec in memory

Before writing, mentally (or via lint) verify:

- All required fields still present and non-empty
- `hypotheses[].id` values still unique
- `actions[].supports` entries still reference valid hypothesis ids
- `execution_mode` still `critical`
- `required_evidence` items still describe observable outputs, not source artifacts

If the project has the ForgeMySpec package available, write the amended spec to a temp path first and lint it:

```bash
python - <<'EOF'
from forgemyspec.linting import lint_spec, format_lint_report
from forgemyspec.generator import load_spec

spec_data = load_spec("/tmp/spec-amended.yaml")
report = lint_spec(spec_data)
print(format_lint_report(report))
EOF
```

Fix any lint errors before showing the diff.

### 5. Show the diff and get approval

Present the delta clearly before writing to the real spec path:

```
PROPOSED CHANGES TO spec.yaml
──────────────────────────────
- hypotheses[2].confidence: 0.8
+ hypotheses[2].confidence: 0.4

- "Returns exit code 0"
+ "Returns exit code 0 and prints parsed result to stdout"

+ constraints:
+   - "Must handle Unicode input up to 4-byte codepoints"
```

Then ask: **"Apply these changes?"**

Do not write until the user confirms (or the context makes approval unambiguous).

### 6. Write the amended spec

Apply only the delta to the existing file. Do not reformat sections that did not change.

If this is a **scope change** (new requirement added or one removed), bump the patch version:

```
version: "0.1" → "0.2"
```

For surgical fixes (assumption correction, confidence revision), version does not change.

### 7. Re-run lint and package

After writing:

```bash
python - <<'EOF'
from forgemyspec.linting import lint_spec, format_lint_report
from forgemyspec.claude_skill import package_claude_skill
from forgemyspec.generator import load_spec

spec_data = load_spec("<spec-path>")
report = lint_spec(spec_data)
print(format_lint_report(report))
if not report.has_errors:
    package_claude_skill("<spec-path>", "<bundle-dir>")
    print("Bundle re-packaged.")
EOF
```

If lint fails, fix and repeat. Do not leave the spec in a failing state.

### 8. Update CLAUDE.md (only if the change is architecturally significant)

Add a single bullet under **Known Pitfalls** or **Decisions** — only if a future implementer would be surprised without it. Do not log transient state.

---

## Scenarios in detail

### Surgical edit — wrong assumption discovered mid-implementation

1. Read spec, identify the hypothesis or assumption that was falsified.
2. Update `hypotheses[n].confidence` downward or revise its `description` to the corrected understanding.
3. If the action plan still holds, no action changes needed.
4. If actions must change too, update them and re-verify `supports` links.
5. No version bump required unless constraints also change.

### Scope change — user adds or removes a requirement

1. Identify which section changes: `success_criteria`, `constraints`, `required_evidence`, or `actions`.
2. If adding a new requirement that needs a new hypothesis: assign a new unique id, add a supporting action with correct `supports`.
3. If removing: delete the hypothesis, update any `action.supports` that referenced it, warn if this leaves an action with an empty `supports` list.
4. Bump version (patch).

### Major pivot — objective changes

1. **Stop.** Confirm with the user: "This changes the objective — do you want to amend the existing spec or compile a new one with `/forgemyspec`?"
2. If amending: update `objective`, review every hypothesis for continued relevance, update `metadata.source_prompt`.
3. Bump minor version (e.g., `0.1` → `1.0`).
4. Re-run full lint cycle.

---

## What NOT to do

- Do not rewrite the entire spec to "clean it up" — that destroys version history semantics.
- Do not add hypotheses that are negations ("X will NOT be needed") — move those to `constraints`.
- Do not change `hypothesis.id` values unless absolutely necessary — it breaks `action.supports` links.
- Do not remove `execution_mode: critical` — every spec is a high-stakes contract.
- Do not list source code or the implementation itself as `required_evidence`.
