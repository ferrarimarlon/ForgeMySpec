# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: REST Blog API
- Objective: A single-file Python REST API (blog_api.py) using only the standard library (http.server + sqlite3) offering CRUD for blog posts, protected by an X-API-Key header, with JSON bodies, served on localhost:8080.

## Non-Negotiable Guardrails
- Standard library only: no third-party packages.
- All code lives in one file, blog_api.py.
- No users, comments, tags, pagination, PATCH or rate limiting.
- The server binds to localhost only, never 0.0.0.0.
- SQL uses parameterized queries, never string formatting of user input.
- The API key is never hard-coded or logged.

## Decision Rules
- If a requirement is ambiguous, stop and ask the user.
- Anything outside the listed routes is a spec amendment.
- Stop and report when the gate fails twice for the same reason.

## Success Criteria
- Every route behaves as specified in the boundary tests, which run against a real server on an ephemeral port.
- Requests without a valid X-API-Key get 401 and change nothing.
- The gate passes.

## Assumptions
- A post has id (integer, server assigned), title (non-empty string), content (string), created_at and updated_at (UTC ISO-8601 strings).
- The valid API key is read from the environment variable BLOG_API_KEY; the server refuses to start when it is unset or empty.
- The SQLite file path comes from BLOG_DB_PATH and defaults to blog.db; tests use a temporary file or :memory:.
- Routes: POST /posts, GET /posts, GET /posts/{id}, PUT /posts/{id} (full replace), DELETE /posts/{id}.
- Binding is 127.0.0.1:8080 only, plain HTTP, no TLS.

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
