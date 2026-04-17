# CLAUDE.md — Markdown Note-Taker CLI

## Role
Implement note_taker.py strictly from spec.yaml.

## Non-Negotiable Guardrails
- Single file: note_taker.py only.
- stdlib only — no PyYAML, no pip installs.
- Storage: ~/.note-taker/ (os.path.expanduser).
- Filename: "<id>-<slug>.md".
- Frontmatter fields exactly: id, title, tags, created_at, updated_at.
- Subcommands: new, list, show, edit, delete.

## Decision Rules
- id not found → "Note <id> not found", exit 1.
- Slug regex: re.sub(r'[^a-z0-9-]+', '', title.lower().replace(' ', '-'))[:40].
- Empty tags → empty string in frontmatter.
- edit nothing changed → "Nothing to update", exit 0.
- list empty → "No notes found."
- show → print raw file content.

## Known Pitfalls
- Frontmatter split: file content split on "---\n" gives 3 parts: ["", frontmatter_body, content]. Index correctly.
- Parse frontmatter: split lines on ": " with maxsplit=1 to handle values containing colons.
- next_id(): scan all files, parse id field, return max+1; return 1 if no files.
- When editing title, the filename changes (old slug → new slug): must rename file, not just rewrite.
- updated_at must change on any edit; created_at must NOT change.
- tags stored as plain comma-separated string, not YAML list syntax.
