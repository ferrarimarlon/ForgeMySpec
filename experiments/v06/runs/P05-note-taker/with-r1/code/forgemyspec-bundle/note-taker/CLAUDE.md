# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Markdown Note-Taking CLI
- Objective: Single-file stdlib-only Python CLI (note_taker.py) to create, list, show, edit and delete Markdown notes stored with YAML frontmatter in ~/.note-taker/, with search by tag or keyword.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- All code lives in the single file note_taker.py.
- No sync, encryption, or non-Markdown formats.
- Notes are written only under the notes directory; ids with path separators are rejected.

## Decision Rules
- Stop and ask if a requirement conflicts with the stdlib-only or single-file constraint.

## Success Criteria
- All five subcommands work end to end against a temporary notes directory.
- Unit tests in tests/ pass.

## Assumptions
- The notes directory is ~/.note-taker/ and can be overridden by the NOTE_TAKER_DIR environment variable (used by tests).
- Frontmatter is a minimal YAML subset written and parsed by the tool itself (title, tags, created, updated), since stdlib has no YAML parser.
- A note is identified by its file name slug (derived from the title); edit opens $EDITOR (fallback vi).
- Search is case-insensitive; list --tag filters by exact tag, list --search filters by keyword in title or body.

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
