# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Directory Organizer
- Objective: A single-file, stdlib-only Python program organizer.py that moves the files sitting directly in a target directory into subdirectories named after their extension, once (--once) or continuously (--watch), logging every move to organizer.log.

## Non-Negotiable Guardrails
- Single file organizer.py; Python standard library only, no third-party packages.
- Files inside subdirectories are not touched, and no recursion happens.
- Hidden files (names starting with a dot) are not moved.
- Existing files are never overwritten or deleted.
- No configuration file, no custom extension mapping, no GUI, no daemonization.

## Decision Rules
- If a behavior is not covered by an obligation, stop and request a spec amendment.
- If a test fails, fix organizer.py, never weaken the test.

## Success Criteria
- Running --once on a directory with mixed files leaves each top-level file in its extension subdirectory.
- Every move appends one line to organizer.log naming source and destination.
- --watch organizes files that appear after it starts.
- Hidden files and files already in subdirectories stay where they are.

## Assumptions
- The target directory is a positional argument; it defaults to the current directory.
- The subdirectory name is the lowercase extension without the dot (report.PDF goes to pdf/).
- A file with no extension goes to a subdirectory named no_extension.
- Only the last suffix counts (archive.tar.gz goes to gz/).
- organizer.log is written inside the target directory and is never moved; organizer.py is never moved either.
- If the destination already has a file with the same name, the moved file gets a numeric suffix (name_1.ext) and nothing is overwritten.
- Watch mode polls the directory every --interval seconds (default 2) and stops on Ctrl-C; no third-party watcher is used.
- Subdirectories are never descended into and never moved; only regular files at the top level are organized.

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
