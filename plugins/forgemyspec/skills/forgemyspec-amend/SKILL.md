---
name: forgemyspec-amend
description: Safely amends an existing ForgeMySpec spec.yaml when new information arrives during implementation (wrong assumption, tighter constraint, scope change, weak contract). Proposes only the minimal delta, validates it with lint and shows the diff before writing. Never rewrites the whole spec without the user's explicit approval.
---

# ForgeMySpec: amend safely

Use this when `spec.yaml` already exists and needs to change. To compile from scratch, use `/forgemyspec`.

## When to apply

| Trigger | Scenario |
|---|---|
| Wrong assumption | A hypothesis failed; the spec's model of the system was wrong |
| Tighter constraint | Implementation revealed an edge case no constraint covers |
| Scope change | The user adds, removes or reprioritizes a requirement |
| Confidence revised | Evidence changes a hypothesis's estimate |
| Major pivot | The objective itself changes (needs explicit approval and a new version) |
| Contract wrong | A Dafny clause or test is wrong or weak (a mutant or planted error survived, a proof is impossible as written) |

## Principle

> **Amend the minimum. Never rewrite what is still true.**

The spec is a contract. Unnecessary rewrites erode trust in its history and break traceability.

## Workflow

1. **Read the current spec** and note the `version`, the hypothesis ids and the actions' `supports`.
2. **Understand the change:** what arrived, what was wrong, which scenario applies. For a major pivot, stop and confirm with the user.
3. **Build the minimal delta before touching the file:**

   ```
   DELTA
     hypotheses[2].confidence: 0.8 → 0.4   (evidence contradicted the assumption)
     constraints: + "Must handle Unicode input up to 4-byte codepoints"
   ```

   If a hypothesis id changes, update every `supports` that references it.
4. **Validate it in a scratch copy:**

   ```bash
   PYTHONPATH=src python3 -m forgemyspec lint <scratch>/spec.yaml --formal
   ```

5. **Show the diff and ask: "Apply these changes?"** Do not write before the yes.
6. **Write only the delta.** A scope change bumps the version (`0.1` → `0.2`); a surgical fix does not.
7. **Lint and package again:** `PYTHONPATH=src python3 -m forgemyspec package <bundle>/spec.yaml`.

### When the bundle is already locked

The guards protect the contract, tests, planted errors, the `formal` section, the version and (for spec-only
bundles) the whole spec. To amend:

1. Propose the spec and contract delta the same way: minimal, as a diff.
2. Never weaken a clause just so the implementation verifies. If the clause is wrong, say why with evidence (a counterexample, a requirement the user stated).
3. Request the unlock with `request-approval unlock:<bundle>`; after **the user types the code** in the
   chat, run `unlock <bundle>` and apply the change.
4. Request the new approval with `request-approval lock:<bundle>` (formal) or `approve:<bundle>`
   (spec-only), show the diff next to the code, and run `lock`/`approve` after the user types it.
5. Run `gate <bundle>`.

## What not to do

- Rewrite the whole spec to "clean it up".
- Write negative hypotheses ("X will not be needed"): those go in `constraints`.
- Change hypothesis ids without need.
- Remove `execution_mode: critical`.
- List the source code as `required_evidence`.
- Delete a planted error or lower a policy limit to make the gate pass.
