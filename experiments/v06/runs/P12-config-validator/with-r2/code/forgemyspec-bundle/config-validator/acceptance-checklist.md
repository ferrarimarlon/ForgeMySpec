# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file stdlib-only Python CLI, config_validator.py, that validates a JSON config file against a JSON schema file and reports all errors at once.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A valid config exits 0 and reports no errors.
- [ ] An invalid config lists every violation, one per line, and exits 1.

## Required Evidence
- [ ] Output of the unittest run in tests/ passing.
- [ ] CLI run output on an invalid config showing several errors at once.

## Decision Rules Compliance
- [ ] If a schema keyword outside the listed subset is needed, stop and ask for a spec amendment.
