# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Directory Organizer
- Objective: A single-file, stdlib-only Python program (organizer.py) that moves files from the top level of a target directory into subdirectories named after their extension, either once (--once) or continuously (--watch), logging every move to organizer.log.

## Non-Negotiable Guardrails
- Python standard library only; no third-party packages.
- Everything lives in one file, organizer.py.
- Never recurse into subdirectories and never touch files already inside them.
- Never move hidden files (names starting with a dot).
- Never overwrite an existing file.
- No deletion of files and no GUI or daemonization.

## Decision Rules
- If a behavior is not covered by an obligation, stop and propose a spec amendment.
- If the gate fails, fix the implementation, never the approved tests.

## Success Criteria
- --once organizes the top level of the target and exits with code 0.
- --watch keeps organizing files that appear later until interrupted with Ctrl+C.
- Each move appends one line to organizer.log with a timestamp, source and destination.
- Hidden files and files in subdirectories are left where they are.

## Assumptions
- The subdirectory name is the lowercased extension without the dot (report.PDF goes to pdf/); a file with no extension goes to no_extension/.
- Only the last suffix counts (archive.tar.gz goes to gz/).
- Watch mode polls the directory at a fixed interval (default 2 seconds, --interval); no third-party filesystem events library.
- The target directory is a positional argument; organizer.log is written in the current working directory unless --log is given, and is never moved.
- On a name collision in the destination the file is renamed with a numeric suffix (a.txt becomes a_1.txt); nothing is overwritten.
- Only regular files are moved; directories and symlinks are left untouched.

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
