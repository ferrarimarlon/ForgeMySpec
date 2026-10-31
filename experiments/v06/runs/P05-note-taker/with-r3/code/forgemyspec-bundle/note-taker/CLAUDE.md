# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Markdown note-taking CLI
- Objective: A single-file, stdlib-only Python CLI (note_taker.py) with subcommands new, list, show, edit and delete that stores notes as .md files with YAML frontmatter in ~/.note-taker/ and searches them by tag or keyword.

## Non-Negotiable Guardrails
- Single file note_taker.py; no third-party packages.
- Notes live only in the notes directory; the tool never writes elsewhere.
- No sync, encryption, templates, rendering of Markdown or other subcommands.
- delete never removes anything but the one named note file.

## Decision Rules
- If a requirement needs a dependency outside the standard library, stop and ask.
- If the frontmatter format must handle full YAML, stop and ask for an amendment.

## Success Criteria
- new creates a .md file with frontmatter and prints its id.
- list shows all notes and filters by --tag and --search.
- show prints one note; edit and delete act on one note by id.
- Unknown ids exit with status 1 and a message on stderr.

## Assumptions
- The notes directory is ~/.note-taker/, overridable by the NOTE_TAKER_DIR environment variable so tests never touch the real home.
- Frontmatter holds id, title, tags and created; it is a small YAML subset written and parsed by the script itself, since PyYAML is not stdlib.
- A note is identified by its slug id, which is also its filename stem (<id>.md).
- edit opens the note in $EDITOR (falling back to $VISUAL, then vi) and re-validates the frontmatter afterwards.
- Keyword search is a case-insensitive substring match over title and body; tag search is a case-insensitive exact match.

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
