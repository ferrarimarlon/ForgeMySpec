# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python REST API (blog_api.py) using only http.server and sqlite3, offering CRUD for blog posts with JSON bodies and X-API-Key authentication, served on localhost:8080.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All five post routes behave as specified, with JSON request and response bodies.
- [ ] Every request without a correct X-API-Key is answered 401 and changes nothing.
- [ ] Boundary tests pass against a real server on a temporary database.

## Required Evidence
- [ ] Output of the unittest run showing every boundary test passing.
- [ ] Output of the gate command ending in RESULT: PASS.

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, stop and ask for a spec amendment.
- [ ] If the gate fails, fix the code, never the tests.
