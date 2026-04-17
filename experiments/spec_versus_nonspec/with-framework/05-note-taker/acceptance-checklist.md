# Acceptance Checklist — Markdown Note-Taker CLI

## Scope
- [x] Only note_taker.py produced.
- [x] No external imports (os, pathlib, argparse, datetime, re, sys, typing only).
- [x] All 5 subcommands present: new, list, show, edit, delete.

## File Storage
- [x] Notes stored in NOTES_DIR (~/note-taker/ or override).
- [x] Filename: 1-python-tips.md, 2-grocery-list.md (correct format).
- [x] Frontmatter fields: id, title, tags, created_at, updated_at.

## CRUD
- [x] new creates file with correct frontmatter and body.
- [x] list shows aligned table with all notes.
- [x] list --tag python returns only tagged note.
- [x] list --search eggs finds "Grocery List" by body content.
- [x] show prints full raw file content.
- [x] edit --title renames file (1-python-tips.md → 1-python-tips-tricks.md), updates updated_at, preserves created_at.
- [x] delete removes file; confirms with title.
- [x] show 99 → "Note 99 not found", exit 1.

## Required Evidence
- [x] Full CRUD session captured above.
- [x] created_at preserved (00:04:59), updated_at changed (00:04:59.970) after edit.

## Issues Found During Implementation
- ISSUE-P5-WF-01 | Phase: a5 (validate) | `Path | None` union syntax requires Python 3.10+; environment is 3.9.6.
  Spec said "Python 3.9+" but CLAUDE.md did not warn about this annotation syntax.
  Fix: added `from typing import Optional` and replaced `Path | None` with `Optional[Path]`.
  Severity: HIGH — crashed on startup before any logic ran.
