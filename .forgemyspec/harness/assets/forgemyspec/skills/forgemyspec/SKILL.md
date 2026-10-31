---
name: forgemyspec
description: Compiles a request into a validated operational spec (spec.yaml) and Claude execution artifacts (CLAUDE.md, acceptance checklist, implement command, scope eval seeds), including the `formal` section that maps every requirement to a Dafny obligation or a Python boundary test. Use when the user wants spec-driven development, an execution contract before coding, or less scope drift and hallucination. First step of the ForgeMySpec flow; /forgemyspec-formalize comes next.
---

# ForgeMySpec: compile the spec

You (Claude, in this session) are the compiler. No external LLM or API is called at any step.
The harness in this repository is deterministic: it checks what you write and refuses what is incomplete.

```
/forgemyspec            → spec.yaml (you)                        → harness: lint + package
/forgemyspec-formalize  → contract.dfy + tests.dfy + planted/    → user approves → harness: lock
/forgemyspec-implement  → impl.dfy + Python shell                 → harness: gate → translated Python
```

Harness commands run from the repository root. In this repository use `PYTHONPATH=src`; in projects
installed with `forgemyspec init` use `PYTHONPATH=.forgemyspec/harness`:

```bash
PYTHONPATH=src python3 -m forgemyspec <lint|package|gate|risk> <path>
```

`lock`, `approve`, `unlock` and `init` belong **to the user only**: the guards refuse them when Claude runs them.

## 1. Ground the request

Read the code, tests, README, tickets or MCP sources the request touches before drafting.
Keep only stable facts (paths, interfaces, invariants). See `references/mcp-and-context.md`.
If the request is ambiguous or constraints conflict, ask the user. A wrong spec is worse than no spec.

## 2. Write `spec.yaml`

Write it to `<bundle>/spec.yaml` (for example `./forgemyspec-bundle/<task>/`). The schema is in
`references/spec-schema.md`. The rules the linter enforces:

- `execution_mode: critical`.
- Hypotheses are affirmative and testable. Things that will not be built go in `constraints`.
- Each action links via `supports` only to the hypotheses it advances. Only `validate`/`review`/`test` actions may support all of them.
- `required_evidence` items are observable outputs (test runs, command output), never "the source code".
- `metadata.source_prompt` holds the request. `metadata.scope_contract.must_include` holds short, exact phrases for every non-negotiable requirement; those are the lines of the risk box.
- `formal` decides what will be **proven** and what will be **tested at the boundary**:
  - `formal.module`: the Dafny name of the abstract contract module.
  - One obligation per checkable rule: `id` (`[a-z][a-z0-9_]*`), `kind: dafny | boundary`, `statement`, `hypotheses`, and `must_include` copied **verbatim** from the scope contract.
  - `kind: dafny` for pure logic: rules, invariants, arithmetic, state transitions.
  - `kind: boundary` for I/O, parsing, files, network, and for **enforcing the core's preconditions** (translated code does not check `requires`). Give it `test: <module>.<Class>.<method>`.
  - Every hypothesis and every `must_include` phrase must be covered by at least one obligation.
- Code that does not fit in Dafny (frontends, integrations): make a **spec-only** bundle with
  `scope.paths` (the paths it covers), `scope.tests` and/or `scope.verify_command`.

Quote YAML list items that contain `: `, start with a backtick, or start with a quote character.

## 3. Lint and package

```bash
PYTHONPATH=src python3 -m forgemyspec lint <bundle>/spec.yaml --formal
PYTHONPATH=src python3 -m forgemyspec package <bundle>/spec.yaml
```

Fix every error, and every warning you can, then repeat. `package` writes `CLAUDE.md`,
`acceptance-checklist.md`, `.claude/commands/implement-from-spec.md` and `evals/scope_drift_cases.yaml`
next to the spec. Generated bundles never go in `.claude/skills/`.

## 4. Hand off

Show the user the obligations table (id, kind, statement) and the assumptions. A formal bundle continues with
`/forgemyspec-formalize`; a spec-only bundle is approved with `request-approval approve:<bundle>`: the user types the code in the chat, then you run `approve <bundle>`.
