# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Markdown note-taking CLI
- Objective: A single-file, stdlib-only Python CLI (note_taker.py) with subcommands new, list, show, edit and delete that stores notes as .md files with YAML frontmatter in ~/.note-taker/ and finds notes by tag or keyword.

## Non-Negotiable Guardrails
- Standard library only; no third-party imports.
- All code lives in the single file note_taker.py.
- No sync, encryption, rendering to HTML or network access.
- No notes are stored outside the notes directory.

## Decision Rules
- If a requirement needs a non-stdlib module, stop and ask.
- If a new subcommand or storage format is wanted, amend the spec first.

## Success Criteria
- All five subcommands work end to end against a temporary notes directory.
- Unit tests for every obligation pass.

## Assumptions
- Notes dir is ~/.note-taker/, overridable by the NOTE_TAKER_DIR environment variable so tests never touch the real home.
- A note is identified by a slug id derived from its title, used as the file name <id>.md.
- Frontmatter is a simple subset of YAML (title, tags as a flow list, created) written and parsed by hand, since PyYAML is not stdlib.
- edit opens the note in $EDITOR (fallback vi); tests set EDITOR to a script.
- Python 3.9 or newer.

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- (record stable architecture or policy decisions here)

## Known Pitfalls
- (record recurring implementation failure modes here)
