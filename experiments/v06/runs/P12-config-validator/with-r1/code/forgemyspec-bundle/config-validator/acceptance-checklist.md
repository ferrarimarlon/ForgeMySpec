# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (config_validator.py) that validates a JSON config file against a JSON schema file and reports every error at once.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] Running the CLI on an invalid config prints every violation, one per line, and exits 1.
- [ ] Running the CLI on a valid config exits 0.

## Required Evidence
- [ ] unittest run of tests/ with all tests passing
- [ ] CLI output on a sample invalid config listing several errors at once

## Decision Rules Compliance
- [ ] If a schema keyword outside the listed subset is needed, stop and ask for a spec amendment.
- [ ] If a check cannot be tested at the boundary, stop and escalate.
