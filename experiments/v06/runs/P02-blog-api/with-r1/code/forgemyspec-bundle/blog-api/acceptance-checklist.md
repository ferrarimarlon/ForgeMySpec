# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file blog_api.py exposing CRUD for posts over JSON on localhost:8080, protected by X-API-Key, using only http.server and sqlite3.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] All five post routes behave as specified and the boundary tests pass.
- [ ] Requests without a valid X-API-Key never reach the database.

## Required Evidence
- [ ] Output of the unittest run over tests_py showing all tests passing.
- [ ] Output of a lint run of the spec with --formal showing no errors.

## Decision Rules Compliance
- [ ] If a behavior is not covered by an obligation, ask before adding it.
- [ ] Stop and ask if the API key source or post fields need to differ from the assumptions.
