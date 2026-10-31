# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: REST Blog API
- Objective: A single-file Python REST API (blog_api.py) using only http.server and sqlite3, offering CRUD for blog posts with JSON bodies and X-API-Key authentication, served on localhost:8080.

## Non-Negotiable Guardrails
- Only the Python standard library; no third-party packages.
- Everything lives in the single file blog_api.py.
- The server binds to 127.0.0.1, never to 0.0.0.0.
- SQL uses parameterized queries only, never string formatting of user input.
- No HTTPS, no CORS, no pagination, no user accounts.

## Decision Rules
- If a behavior is not covered by an obligation, stop and ask for a spec amendment.
- If the gate fails, fix the code, never the tests.

## Success Criteria
- All five post routes behave as specified, with JSON request and response bodies.
- Every request without a correct X-API-Key is answered 401 and changes nothing.
- Boundary tests pass against a real server on a temporary database.

## Assumptions
- A post has id (integer, assigned by the server), title (non-empty string), body (non-empty string), created_at and updated_at (UTC ISO-8601 strings).
- Routes: POST /posts, GET /posts, GET /posts/{id}, PUT /posts/{id} (full replace), DELETE /posts/{id}.
- The valid API key comes from the environment variable BLOG_API_KEY; the server refuses to start when it is unset or empty.
- The SQLite file path comes from BLOG_DB_PATH, default blog.db; tests use a temporary file.
- Binding is 127.0.0.1 port 8080 by default; tests may start the server on another port through the factory function.
- No pagination, no users, no comments, no tags.

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
