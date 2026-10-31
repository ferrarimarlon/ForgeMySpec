# CLAUDE.md — Project Memory

## Framework

This project is **ForgeMySpec**: a Claude-Code-native harness that turns a request into a spec, a
user-approved Dafny contract, and a verified implementation translated to Python. All implementation work
in this repository follows that flow.

## Default Agent

The `forgemyspec-default` agent (`plugins/forgemyspec/agents/forgemyspec-default.md`, symlinked under
`.claude/agents/`) is the entry point for development tasks. It preloads the `forgemyspec`,
`forgemyspec-formalize`, `forgemyspec-implement`, and `forgemyspec-amend` skills.

## Spec-First Rule

**No code without a spec, and no implementation without a locked contract.**

| Situation | Action |
|---|---|
| No spec exists for the task | `/forgemyspec` |
| Spec exists, no locked contract | `/forgemyspec-formalize` (user approves, then `lock`) |
| Contract locked | `/forgemyspec-implement` (until the gate passes) |
| Spec or contract needs a targeted update | `/forgemyspec-amend`: propose the delta only, lint, get approval, relock if the contract changed |

## Claude is the only LLM

Never call an external LLM API. Claude writes `spec.yaml`, `contract.dfy`, `tests.dfy` and `impl.dfy`
in the session; the harness only checks them:

```bash
PYTHONPATH=src python3 -m forgemyspec lint <spec.yaml> [--formal]
PYTHONPATH=src python3 -m forgemyspec package <spec.yaml>
PYTHONPATH=src python3 -m forgemyspec lock <bundle> [--check]
PYTHONPATH=src python3 -m forgemyspec gate <bundle>
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Project Layout

```
src/forgemyspec/         deterministic harness (lint, coverage, Dafny lint, lock, gate, mutation)
plugins/forgemyspec/     canonical skills + default agent (symlinked into .claude/)
.claude/                 settings.json (defaultAgent), symlinks to plugins/forgemyspec
examples/budget-core/    end-to-end formal bundle; the gate must pass on it
experiments/             historical benchmark data and the mini-os case study (pre-Dafny)
forgemyspec-bundle/      the spec this harness version was built from
tests/                   harness tests
```

## Conventions

- Generated bundles go in `./forgemyspec-bundle/<task>/` or another task-named directory, never in `.claude/skills/`.
- `CLAUDE.md` files (this one and those inside bundles) store only stable decisions and known pitfalls.
- Runtime dependencies: Python 3.9+ stdlib and PyYAML. Dafny 4.x is the only external toolchain.
- `generated/` is written by the gate and is gitignored; never edit it by hand.

## Known Pitfalls

- Dafny skips verification of files reached only through `include`: always pass every `.dfy` file explicitly. The harness does.
- `dafny audit` exits 0 even with findings; read the count.
- Translated Python does not check `requires`; enforce preconditions in the shell as boundary obligations.
- More in `plugins/forgemyspec/skills/forgemyspec/references/dafny-patterns.md`.
- Do not add external dependencies unless the spec's `must_include` calls for them.
- Quote YAML list items containing `: ` or starting with a backtick; unquoted, they parse as mappings or fail.
