# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file, stdlib-only Python CLI (config_validator.py) that validates a JSON config file against a JSON schema file and reports every violation at once, with nested fields addressed in dot notation.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] A config violating several rules yields one error line per violation in a single run.
- [ ] A valid config exits 0 and an invalid one exits 1.

## Required Evidence
- [ ] unittest run of tests/ passing, covering each rule and the CLI exit codes
- [ ] forgemyspec gate output ending in RESULT: PASS

## Decision Rules Compliance
- [ ] If a schema keyword outside the listed subset is needed, stop and amend the spec.
- [ ] If the gate fails, fix the implementation, never the approved spec.
