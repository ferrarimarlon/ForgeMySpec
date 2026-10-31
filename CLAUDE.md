# CLAUDE.md — Project Memory

## Framework

This project is **ForgeMySpec**: a Claude-Code-native harness that turns a request into a spec, a
user-approved Dafny contract and a verified implementation translated to Python. All implementation work in this
repository follows that flow.

## Default Agent

The `forgemyspec-default` agent (`plugins/forgemyspec/agents/forgemyspec-default.md`, symlinked under
`.claude/agents/`) is the entry point for development tasks. It preloads the `forgemyspec`,
`forgemyspec-formalize`, `forgemyspec-implement` and `forgemyspec-amend` skills.

## Spec-First Rule

**No code without a spec, and no implementation without a locked contract.**

| Situation | Action |
|---|---|
| No spec exists for the task | `/forgemyspec` |
| Formal spec exists, no locked contract | `/forgemyspec-formalize` (the user approves by typing the `request-approval` code in the chat; then `lock`) |
| Spec-only bundle not approved | `request-approval approve:<bundle>`; the user types the code; then `approve` |
| Contract locked | `/forgemyspec-implement` (until the gate passes) |
| Spec or contract needs a targeted update | `/forgemyspec-amend`: propose the delta only, lint, get approval as a typed code; then `unlock` and `lock`/`approve` |

## Claude is the only LLM

Never call an external LLM API. Claude writes `spec.yaml`, `contract.dfy`, `tests.dfy`, `planted/` and `impl.dfy`
in the session; the harness only checks them:

```bash
PYTHONPATH=src python3 -m forgemyspec lint <spec.yaml> [--formal]
PYTHONPATH=src python3 -m forgemyspec package <spec.yaml>
PYTHONPATH=src python3 -m forgemyspec gate <bundle>
PYTHONPATH=src python3 -m forgemyspec risk
PYTHONPATH=src python3 -m forgemyspec kernel --check
PYTHONPATH=src python3 -m unittest discover -s tests
```

`lock`, `approve`, `unlock` and `init` need the user's approval: `request-approval <action>:<target>` prints a code, the
user types it in the chat, and only then the command runs (or the user runs it in their own terminal). A plain "yes"
is not an approval.

## Project Layout

```
src/forgemyspec/         deterministic harness (lint, coverage, Dafny lint, locks, gate, mutation, guards, risk box, init)
src/forgemyspec/_kernel/ trust kernel translated from Dafny (generated; never edit by hand)
plugins/forgemyspec/     canonical skills + default agent (symlinked into .claude/)
.claude/                 settings.json, symlinks to plugins/forgemyspec
examples/budget-core/    end-to-end formal bundle; the gate must pass on it
forgemyspec-bundle/      specs this harness was built from: v0.1 (root), enforcement (v0.5), kernel
experiments/             historical benchmark data and the mini-os case study (pre-Dafny)
tests/                   harness tests
```

## Conventions

- Everything in the product is in English: code, identifiers, messages, specs and documentation.
- Every user-facing text lives in `src/forgemyspec/messages.py`.
- Generated bundles go in `./forgemyspec-bundle/<task>/` or another task-named directory, never in `.claude/skills/`.
- `CLAUDE.md` files store only stable decisions and known pitfalls.
- Runtime dependencies: Python 3.9+ stdlib and PyYAML. Dafny 4.x is the only external toolchain.
- `generated/` and `.forgemyspec/state/` are gitignored; never edit them by hand.
- After changing the kernel bundle, run `python -m forgemyspec kernel` and commit `_kernel/`.

## Known Pitfalls

- Dafny skips verification of files reached only through `include`: always pass every `.dfy` file explicitly. The harness does.
- `dafny audit` exits 0 even with findings; read the count.
- Translated Python does not check `requires`; enforce preconditions in the shell as boundary obligations.
- More in `plugins/forgemyspec/skills/forgemyspec/references/dafny-patterns.md`.
- Do not add external dependencies unless the spec's `must_include` calls for them.
- Quote YAML list items containing `: ` or starting with a backtick; unquoted, they parse as mappings or fail.
