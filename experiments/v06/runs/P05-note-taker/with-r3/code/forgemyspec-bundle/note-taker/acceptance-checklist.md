# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (note_taker.py) with subcommands new, list, show, edit and delete that stores notes as .md files with YAML frontmatter in ~/.note-taker/ and searches them by tag or keyword.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] new creates a .md file with frontmatter and prints its id.
- [ ] list shows all notes and filters by --tag and --search.
- [ ] show prints one note; edit and delete act on one note by id.
- [ ] Unknown ids exit with status 1 and a message on stderr.

## Required Evidence
- [ ] unittest run of tests/ showing every boundary test passing
- [ ] gate output ending in RESULT: PASS

## Decision Rules Compliance
- [ ] If a requirement needs a dependency outside the standard library, stop and ask.
- [ ] If the frontmatter format must handle full YAML, stop and ask for an amendment.
