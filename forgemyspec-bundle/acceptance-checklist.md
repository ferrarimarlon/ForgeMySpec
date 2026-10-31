# Acceptance Checklist

## Scope
- [x] Objective implemented: the repo runs inside Claude Code (skills + agent), the LLM CLI path is gone, and the deterministic harness proves, tests, audits, mutation-checks, locks and translates Dafny bundles.
- [x] No unrequested features. Additions beyond the literal action list, each needed to make an action work:
  - `lock --check`: the formalize step needs pre-lock checks before `impl.dfy` exists.
  - The lock also covers `tests.dfy` and the `formal` section, not only `contract.dfy`. This is stricter than h5.
  - `expect` (outside tests) and `{:only}` are banned. Both were found as soundness loopholes while probing Dafny.
  - Dafny tests run on the Python target, the backend the core ships on.
  - The agent's stale `model: claude-opus-4-6` pin was removed, so it inherits the session model.
  - `docs/cli-demo.png`, a screenshot of the removed CLI, was removed.
- [x] Assumptions are explicit in spec.yaml. The riskiest one (h2, refinement split) was tested in a prototype before building on it.

## Success Criteria
- [x] Unit tests pass with OPENAI_API_KEY and ANTHROPIC_API_KEY unset (47 tests). The harness makes no network calls, but the run was not inside a sandbox with networking disabled.
- [x] The external-API grep prints nothing.
- [x] `gate examples/budget-core` exits 0 with every stage PASS (toolchain and translate included).
- [x] All five injected faults fail at the named stage with exit 1. They run through the CLI and as unit tests in `tests/test_gate.py`.
- [x] The mutation stage reports candidates, killed/scored, invalid, and each survivor as `impl.dfy:line:col` with its operator: 14/14 killed on budget-core. `test_weak_contract_lets_mutants_survive` shows survivors being reported and failing the gate.
- [x] All 20 spec.yaml files load and lint with 0 errors.
- [x] All 31 repository paths referenced in README.md and CLAUDE.md exist.
- [ ] **Pending:** CI installs Dafny and runs the tests and the gate. The workflows are written and parse as YAML, and the bundle-discovery logic was simulated locally. They have not run on GitHub yet because nothing was pushed.

## Required Evidence
- [x] Unit-test output, API keys unset: 47 tests, OK.
- [x] External-API grep: empty (exit 1).
- [x] Full gate report for budget-core: all PASS, mutation 14/14.
- [x] Gate output for the five faults: dafny-lint, dafny-lint + contract-lock, contract-lock, obligation-coverage, toolchain; exit 1 each.
- [x] Boundary tests against generated/core-py: 4 tests OK.
- [x] Spec lint over every spec.yaml: total errors 0.
- [x] Doc path check: 31 checked, 0 missing.
- [ ] `dafny --version`: 4.11.0 locally. **Pending** from the CI log.

## Decision Rules Compliance
- [x] Refinement split: worked in Dafny 4.11.0, so the single-file fallback was not needed.
- [x] Equivalent mutants: supported only with a stated reason, listed in the report; a missing reason fails the gate. The threshold was not lowered.
- [x] Non-formalizable requirements: the CLI parsing and the `start >= 0` precondition are boundary obligations with named tests.
- [x] Ambiguous contract semantics: none came up. Note: Claude locked the **example** contract, based on the user's approval of the spec, which listed its rules. Real bundles require explicit approval of the contract itself before `lock`.
- [x] Removed modules: only tests of deleted code (generator, dotenv, providers) were removed. The policy, lint, packaging and scope-eval tests were kept and adapted.
- [x] No stage needs network or an API key.
