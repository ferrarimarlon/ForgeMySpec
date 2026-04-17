# CLAUDE.md — REST Blog API

## Role
Implement blog_api.py strictly from spec.yaml. No scope expansion.

## Non-Negotiable Guardrails
- Single file: blog_api.py only.
- stdlib only — no pip installs.
- Endpoints exactly as in spec (5 routes).
- Auth: X-API-Key header = "secret123".
- DB file: blog.db in cwd.

## Decision Rules (from spec)
- Missing/wrong key → 401 JSON.
- Unknown route → 404 JSON.
- Wrong method → 405 JSON.
- POST missing fields → 400 JSON with field list.
- PUT updates only provided fields + updated_at.
- DELETE → 204 empty body always.
- Datetimes: UTC ISO-8601.

## Discovered Pitfalls (added post-implementation)
- Route loop must NOT short-circuit on method mismatch — continue iterating to find matching method on same path pattern.
- `get_post_by_id(cur.lastrowid)` inside `with conn:` block reads before commit; always capture lastrowid, exit with block, then query.

## Pre-existing Pitfalls
- BaseHTTPRequestHandler.rfile.read(n) blocks if Content-Length missing — always read Content-Length header first.
- send_response() must be followed by send_header() then end_headers() before wfile.write().
- http.server does not parse path params — use re.match on self.path.
- sqlite3 connection must be created per-request (not shared across threads if ThreadingHTTPServer is used).
- DELETE response: call send_response(204) then end_headers() with NO body write — writing empty body causes issues.
