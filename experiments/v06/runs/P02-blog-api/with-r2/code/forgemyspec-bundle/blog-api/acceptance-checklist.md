# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python REST API (blog_api.py) using only the standard library (http.server + sqlite3) offering CRUD for blog posts, protected by an X-API-Key header, with JSON bodies, served on localhost:8080.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Every route behaves as specified in the boundary tests, which run against a real server on an ephemeral port.
- [ ] Requests without a valid X-API-Key get 401 and change nothing.
- [ ] The gate passes.

## Required Evidence
- [ ] Output of the unittest run in tests/ showing all boundary tests passing.
- [ ] Gate report with RESULT: PASS.

## Decision Rules Compliance
- [ ] If a requirement is ambiguous, stop and ask the user.
- [ ] Anything outside the listed routes is a spec amendment.
- [ ] Stop and report when the gate fails twice for the same reason.
