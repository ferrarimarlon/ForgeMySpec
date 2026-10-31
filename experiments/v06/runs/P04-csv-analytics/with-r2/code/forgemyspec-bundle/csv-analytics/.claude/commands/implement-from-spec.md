Implement strictly from `./spec.yaml`, `./CLAUDE.md` and the locked `./contract.dfy` + `./tests.dfy`.

Execution steps:
1. Confirm `contract.lock` exists. If it does not, run /forgemyspec-formalize and get the user's approval first.
2. Never edit `contract.dfy`, `tests.dfy`, `planted/` or the spec's `formal` section; changes go through /forgemyspec-amend.
3. Write `impl.dfy` as a module refining the contract, then `shell/` and `tests_py/` for boundary obligations.
4. From the repository root, run `python3 -m forgemyspec gate <path-to-this-bundle>` until every stage passes.
5. Return a final report with: changed files, the full gate report, assumptions made, and residual risks.
