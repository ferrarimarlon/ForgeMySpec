# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (note_taker.py) with subcommands new, list, show, edit and delete that stores notes as .md files with YAML frontmatter in ~/.note-taker/ and finds notes by tag or keyword.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All five subcommands work end to end against a temporary notes directory.
- [ ] Unit tests for every obligation pass.

## Required Evidence
- [ ] Output of python3 -m unittest showing all note_taker tests passing.
- [ ] Gate report with RESULT: PASS.

## Decision Rules Compliance
- [ ] If a requirement needs a non-stdlib module, stop and ask.
- [ ] If a new subcommand or storage format is wanted, amend the spec first.
