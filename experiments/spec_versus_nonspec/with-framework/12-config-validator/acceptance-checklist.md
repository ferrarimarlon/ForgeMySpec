# Acceptance Checklist — Config Validator

- [ ] type check rejects coerced values (string != int)
- [ ] required missing fields reported
- [ ] dot-notation nested keys resolved
- [ ] min/max validated for numerics
- [ ] enum validated
- [ ] pattern validated (regex)
- [ ] items_type validated for lists
- [ ] ALL errors reported before exit 1
