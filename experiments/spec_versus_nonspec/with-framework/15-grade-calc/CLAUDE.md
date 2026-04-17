# CLAUDE.md — Implementation Notes

## Pitfalls tracked from spec
- Python 3.9 only: no `X | Y` union types, no `match` statements
- Use `python3` binary
- All monetary rounding: use `round(value, 2)` at each step
- Stdlib only: no external dependencies
