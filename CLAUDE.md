# CLAUDE.md — Project Memory

## Framework

This project uses **ForgeMySpec** as its default development framework. All implementation work must follow the spec-first workflow.

## Default Agent

The `forgemyspec-default` agent (`plugins/forgemyspec/agents/forgemyspec-default.md`, symlinked under `.claude/agents/`) is the entry point for all development tasks. It:
- Preloads the `forgemyspec`, `forgemyspec-implement`, and `forgemyspec-amend` skills
- Enforces spec compilation before any code is written
- Routes to the correct skill based on whether a `spec.yaml` already exists

## Spec-First Rule

**Do not write code without a spec.**

| Situation | Action |
|---|---|
| No spec exists for the task | Run `/forgemyspec` first |
| Spec exists | Run `/forgemyspec-implement` |
| Spec needs a targeted update | Run `/forgemyspec-amend` — propose delta only, lint, then confirm |
| Spec is stale or ambiguous | Ask user to update `spec.yaml` before proceeding |

## Conversation Board

The reply is the board. For each user request: add a requirement to `forgemyspec-board.yaml` (status, the user's
words, checkable steps = its contract), run `PYTHONPATH=src python3 -m forgemyspec.board start R<n>`, work on it,
run `verify` when steps have checks, and end the reply with the output of
`PYTHONPATH=src python3 -m forgemyspec.board`, whole, in a code block, plus at most one line of text. Explain only
when the user asks ("abre R<n>" → `python3 -m forgemyspec.board R<n>`). See `/forgemyspec-board`.

## Amend Workflow

Use `/forgemyspec-amend` when implementation reveals something the spec got wrong — a failed assumption, a missing constraint, a scope change. The rule:

1. **Propose only the delta** — never rewrite the whole spec.
2. **Validate first** — lint the amended spec before showing it to the user.
3. **Show diff, get approval** — do not write until the user confirms.
4. **Version bump** on scope changes (`0.1 → 0.2`); not required for surgical fixes.
5. **Re-package** the bundle after writing.

## Project Layout

```
.
├── CLAUDE.md                          ← you are here (project memory)
├── plugins/forgemyspec/                 ← canonical skills + default agent source (symlinked into .claude/)
│   ├── agents/forgemyspec-default.md
│   └── skills/{forgemyspec,forgemyspec-implement,forgemyspec-amend}/
├── .claude/
│   ├── settings.json                  ← `defaultAgent`: forgemyspec-default
│   ├── agents/forgemyspec-default.md    ← symlink → plugins/forgemyspec/agents/…
│   └── skills/                        ← symlinks → plugins/forgemyspec/skills/…
├── examples/                          ← example ForgeMySpec bundles
│   ├── sample-bundle/                 ← parser CLI example
│   └── mini-os/                       ← minimal x86 OS example
└── src/                               ← ForgeMySpec Python package
```

## Spec Generation Rule

**Claude is the LLM — never call an external API to generate the spec.**

The `src/forgemyspec` CLI splits into two parts:
- `build_spec` → LLM call (replaced by Claude directly authoring the spec)
- `lint_spec` + `package_claude_skill` → deterministic, no API key needed

Workflow for every spec:
1. Read `src/forgemyspec/models.py` and `plugins/forgemyspec/skills/forgemyspec/references/spec-schema.md` to ground the schema
2. Author `spec.yaml` content directly (Claude replaces the LLM call)
3. Write it to `./forgemyspec-bundle/spec.yaml`
4. Run lint + packaging via the `src/` package:

```bash
python - <<'EOF'
from forgemyspec.linting import lint_spec, format_lint_report
from forgemyspec.claude_skill import package_claude_skill
from forgemyspec.generator import load_spec

spec_data = load_spec("forgemyspec-bundle/spec.yaml")
report = lint_spec(spec_data)
print(format_lint_report(report))
if not report.has_errors:
    package_claude_skill("forgemyspec-bundle/spec.yaml", "forgemyspec-bundle")
    print("Bundle packaged.")
EOF
```

5. Fix any lint errors, then implement via `/forgemyspec-implement`

Do not run `forgemyspec --prompt ...` — that triggers an unnecessary external LLM call.

## Conventions

- Generated bundles go in `./forgemyspec-bundle/` or a task-named subdirectory — never directly in `.claude/skills/`.
- `CLAUDE.md` files (this one and those inside bundles) store only stable decisions and known pitfalls — not transient logs or scratch notes.
- Scope drift is checked against `evals/scope_drift_cases.yaml` in each bundle.

## Known Pitfalls

- Do not add external dependencies unless the spec's `must_include` explicitly calls for a library.
- Amending a spec mid-implementation is allowed via `/forgemyspec-amend` — but always propose the minimal delta and get user approval before writing. Do not silently rewrite the spec.
