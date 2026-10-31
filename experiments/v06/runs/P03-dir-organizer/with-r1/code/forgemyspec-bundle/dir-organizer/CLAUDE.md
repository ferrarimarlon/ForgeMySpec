# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Directory Organizer
- Objective: A single-file, stdlib-only Python tool (organizer.py) that moves files from the top level of a target directory into subdirectories named after their extension, once (--once) or continuously (--watch), logging every move to organizer.log.

## Non-Negotiable Guardrails
- Single file organizer.py; Python standard library only; no third-party packages.
- No recursion into subdirectories; no deletion of files; no overwriting of existing files.
- No GUI, no daemonization, no configuration file, no custom extension mapping.

## Decision Rules
- If a behavior is not covered by an obligation, stop and amend the spec instead of adding it.
- If stdlib cannot do something, escalate to the user; do not add a dependency.

## Success Criteria
- Running --once on a directory with mixed files moves each visible top-level file into its extension subdirectory.
- Every move appends a line to organizer.log.
- Hidden files and files already in subdirectories are left in place.

## Assumptions
- Subdirectory name is the lowercased extension without the dot (report.PDF goes to pdf/).
- Files with no extension go to a subdirectory named no_extension.
- Hidden means the file name starts with a dot; hidden files are never moved.
- Files already in subdirectories are never touched; only top-level regular files of the target are considered.
- Name collision at the destination: the file is renamed with a numeric suffix (name_1.ext); nothing is overwritten.
- organizer.log is written in the current working directory (option --log overrides the path); if it sits in the target it is not moved.
- Watch mode is polling-based (stdlib has no filesystem events), with a configurable interval defaulting to 2 seconds.
- CLI: organizer.py TARGET (--once | --watch) [--interval SECONDS]; exactly one mode is required.

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
