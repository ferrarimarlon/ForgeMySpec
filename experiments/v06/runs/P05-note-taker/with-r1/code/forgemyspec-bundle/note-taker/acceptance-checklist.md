# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Single-file stdlib-only Python CLI (note_taker.py) to create, list, show, edit and delete Markdown notes stored with YAML frontmatter in ~/.note-taker/, with search by tag or keyword.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All five subcommands work end to end against a temporary notes directory.
- [ ] Unit tests in tests/ pass.

## Required Evidence
- [ ] Output of python3 -m unittest discover -s tests showing all tests pass.
- [ ] Output of the gate command for the bundle.

## Decision Rules Compliance
- [ ] Stop and ask if a requirement conflicts with the stdlib-only or single-file constraint.
