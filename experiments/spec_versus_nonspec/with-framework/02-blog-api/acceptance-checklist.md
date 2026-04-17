# Acceptance Checklist — REST Blog API

## Scope
- [x] Only blog_api.py produced.
- [x] No external imports (http.server, sqlite3, json, re, os, datetime, timezone).
- [x] Exactly 5 route patterns implemented.

## Auth
- [x] Valid X-API-Key → request proceeds.
- [x] Missing X-API-Key → 401 JSON {"error": "Unauthorized"}.
- [x] Wrong X-API-Key → 401 JSON.

## Endpoints
- [x] GET /posts → 200 JSON array.
- [x] POST /posts → 201 JSON with created post (body correct after commit fix).
- [x] GET /posts/<id> → 200 JSON or 404 JSON.
- [x] PUT /posts/<id> → 200 JSON with updated post + new updated_at.
- [x] DELETE /posts/<id> → 204 empty body.
- [x] Unknown route → 404 JSON {"error": "Not found"}.

## Persistence
- [x] blog.db created on first request (12K).
- [x] Data persists across server restarts.

## Required Evidence
- [x] curl transcript: POST (201), GET list (200), GET one (200), PUT (200), DELETE (204).
- [x] curl without key → 401.
- [x] curl /nonexistent → 404.
- [x] ls -lh blog.db: 12K present.
- [x] Server started without error output.

## Issues Found During Implementation
- ISSUE-P2-WF-01 | Phase: a5 (validate) | Routing short-circuit: first pattern match returned 405 before checking subsequent routes with correct method.
  Root cause: return inside loop on method mismatch instead of continuing.
  Fix: two-pass — collect path_matched flag, return 405 only after full loop.
  Severity: HIGH — blocked POST/PUT/DELETE entirely.

- ISSUE-P2-WF-02 | Phase: a5 (validate) | POST returned null body (HTTP 201).
  Root cause: get_post_by_id() called inside `with conn:` block before commit, so second connection saw no row.
  Fix: capture lastrowid before exiting with block; call get_post_by_id after commit.
  Severity: MEDIUM — status correct but body wrong.
  Note: CLAUDE.md pitfall about per-request connections did NOT catch this specific case.
