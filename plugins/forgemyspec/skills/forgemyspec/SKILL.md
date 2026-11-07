---
name: forgemyspec
description: Compiles a human requirement into a validated operational spec (spec.yaml) and Claude execution artifacts (CLAUDE.md, acceptance checklist, implement command, scope eval seeds). Use when the user wants spec-driven development, a concrete execution contract before coding, or to reduce scope drift. Prefer this skill inside Claude Code where MCP tools can supply repository, docs, or ticket context before drafting the spec.
---

# ForgeMySpec (in-session compiler)

This skill mirrors the **ForgeMySpec** pipeline: **gather context → structured spec → lint discipline → packaged artifacts**. Running inside Claude, you use **MCPs and native tools** for context that the external CLI cannot see automatically.

## When to apply

- The user asks for a spec, execution contract, or “ForgeMySpec-style” bundle before implementation.
- The task needs explicit constraints, success criteria, evidence, and traceability (actions ↔ hypotheses).
- The user wants to leverage **MCP-connected** sources (codebase, issues, wikis, APIs) while authoring the spec.

## Workflow

### 1. Pull context (MCPs first)

Before drafting `spec.yaml`, use whatever MCP or workspace tools are available to ground the requirement:

- Repository layout, existing modules, tests, CI.
- Prior decisions (ADRs, README, tickets).
- External docs or APIs the feature must integrate with.

Summarize only **stable facts** the spec should reference (file paths, interfaces, invariants). See `references/mcp-and-context.md`.

### 2. Author `spec.yaml`

Follow the schema in `references/spec-schema.md`. Include:

- Clear `objective`, `constraints`, `success_criteria`, `required_evidence`.
- `hypotheses` with ids and `confidence` in `[0, 1]`.
- `actions` with `supports` linking to hypothesis ids (traceability).
- `metadata.source_prompt` (the user’s request text) and optional `scope_contract` if in/out scope is known.

Match team policy if `.forgemyspec-policy.yaml` exists in the project (minimum counts, required metadata fields, allowed action types).

### 3. Validate (deterministic gate)

If the **ForgeMySpec Python package** is installed in the environment, run the CLI on the saved spec path to run LLM-assisted generation or to lint:

```bash
forgemyspec --prompt "..." --output-dir ./forgemyspec-bundle
```

For a spec already on disk, the codebase linter is `forgemyspec.linting.lint_spec`—in practice, ensure structural checks manually or run project tests if present.

When the CLI is **not** available, self-check against `references/spec-schema.md`: required top-level keys, non-empty strings, hypothesis/action id uniqueness, `supports` ⊆ hypothesis ids, boolean `requires_confirmation`.

### 4. Emit the artifact bundle

Write the same files the external packager produces (see repository `src/forgemyspec/claude_skill.py` for canonical renderers):

| File | Purpose |
| --- | --- |
| `spec.yaml` | Source of truth |
| `CLAUDE.md` | Persistent memory + guardrails snapshot |
| `.claude/commands/implement-from-spec.md` | Implementation entrypoint |
| `acceptance-checklist.md` | Delivery gate |
| `evals/scope_drift_cases.yaml` | Scope drift eval seeds |

Use a dedicated output directory (for example `./forgemyspec-bundle` or `./forgemyspec-skill`) so project skills under `.claude/skills/` stay separate from generated bundles.

### 5. Implementation handoff

Point the user or a follow-up turn to `references/implement-from-spec-workflow.md` and the generated `implement-from-spec` command.

## Relationship to the external CLI

- **This skill**: Claude-native workflow; MCP-rich context; manual or hybrid drafting.
- **CLI (`forgemyspec`)**: Subcontracts LLM draft generation and deterministic lint/package when run from a terminal with API keys.

Both target the **same artifact shapes** so teams can mix terminal compilation and in-session iteration.

## Bundled references

- `references/spec-schema.md` — YAML shape and field roles
- `references/mcp-and-context.md` — How to use MCP context effectively
- `references/implement-from-spec-workflow.md` — Post-spec implementation steps
