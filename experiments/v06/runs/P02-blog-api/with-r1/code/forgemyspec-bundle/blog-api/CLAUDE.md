# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: REST Blog API
- Objective: A single-file blog_api.py exposing CRUD for posts over JSON on localhost:8080, protected by X-API-Key, using only http.server and sqlite3.

## Non-Negotiable Guardrails
- Standard library only: no third-party packages.
- Everything lives in the single file blog_api.py.
- The server binds to 127.0.0.1 port 8080 by default and nothing else.
- No users, comments, tags, pagination or HTML pages.

## Decision Rules
- If a behavior is not covered by an obligation, ask before adding it.
- Stop and ask if the API key source or post fields need to differ from the assumptions.

## Success Criteria
- All five post routes behave as specified and the boundary tests pass.
- Requests without a valid X-API-Key never reach the database.

## Assumptions
- A post has id (integer, assigned by the server), title (non-empty string) and content (string).
- The API key comes from the BLOG_API_KEY environment variable, with a development default of 'dev-key'.
- The database is a SQLite file blog.db by default, overridable by BLOG_DB; tests use a temp file.
- Routes: POST /posts, GET /posts, GET /posts/<id>, PUT /posts/<id>, DELETE /posts/<id>.

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
