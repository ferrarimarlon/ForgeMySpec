# ForgeMySpec plugin

Spec-first development inside Claude Code: Claude writes the spec (and, for critical logic, a Dafny contract),
you approve it in the chat with a short code, and deterministic gates check the work. No external LLM calls.

## Install

```
/plugin marketplace add /Users/marlonferrari/Desktop/ForgeMySpec/plugin
/plugin install forgemyspec@forgemyspec
```

Requirements: Python 3.9+ with PyYAML; Dafny 4.x only for formal (Dafny) bundles.

## What it does

- `/forgemyspec` writes a spec; spec-only by default, Dafny only for critical logic.
- Guards: edits need an approved spec that covers the path; locks, contracts and harness state are protected.
- Approval in the chat: `request-approval` prints a code bound to the content hash; you type it.
- `forgemyspec board`: every request as a requirement, with status bars and the harness vs model share.
- `forgemyspec gate <bundle>` (and `--fast` in the session): lint, tests, Dafny verification, mutation, planted errors.

Harness commands: `PYTHONPATH="<plugin>/harness" python3 -m forgemyspec <command>`.

Built from the ForgeMySpec repository with `scripts/build_plugin.py` (version 0.6.0); do not edit by hand.
