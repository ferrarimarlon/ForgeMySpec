# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: ForgeMySpec as a Claude-Code-native harness with a Dafny formal layer
- Objective: Turn the repository into a clonable project that runs entirely inside Claude Code: Claude authors spec.yaml, then a Dafny contract and a Dafny implementation, and a deterministic Python harness proves, tests, audits, mutation-checks and locks them before translating the verified core to Python. Remove the external-LLM CLI path and fix the defects found in the repository review.

## Non-Negotiable Guardrails
- No code in src/, plugins/ or .github/ calls an external LLM or HTTP API, reads OPENAI_* or ANTHROPIC_* variables, or loads a .env file.
- Harness runtime dependencies are Python >=3.9 standard library plus PyYAML; Dafny 4.x is the only external toolchain.
- The gate fails closed: a missing or too-old dafny binary, a timeout, or an unparsable file is a FAIL with an actionable message, never a skip.
- Banned in any .dfy file of a bundle: `assume`, `{:axiom}`, `{:verify false}`, `{:extern}`, `decreases *`, `requires false`, `ensures true`; bodiless methods or functions are banned in impl.dfy.
- contract.dfy is never edited during the implement phase; any contract change goes through /forgemyspec-amend, explicit user approval and a new contract.lock.
- Translated Python under generated/ is never hand-edited; the hand-written Python I/O shell imports it and stays separate.
- Existing lint codes keep their meaning; new checks use LINT-FORMAL-* (spec level) and LINT-DFY-* (Dafny level) codes.
- Commits stay local; nothing is pushed without an explicit user instruction at that moment.

## Decision Rules
- If the abstract-module refinement split fails to verify or translate in Dafny 4.x, fall back to a single file with `// @contract-begin` / `// @contract-end` regions, lock only those regions, and record the decision in CLAUDE.md.
- If a mutant survives and is semantically equivalent, suppress it only with an `// @equivalent-mutant: <reason>` comment that the gate report lists; never lower the kill-rate threshold to make a run pass.
- If a must_include requirement cannot be expressed in Dafny, declare it as a boundary obligation with a named Python test; never drop it from coverage.
- If contract semantics are ambiguous while formalizing, stop and ask the user before writing contract.lock.
- If removing a module breaks a test that encodes behavior still in scope, keep the behavior and adapt the test.
- If a stage needs network or an API key to pass, treat that as a defect in the harness.

## Success Criteria
- `PYTHONPATH=src python3 -m unittest discover -s tests` passes with no network access and with OPENAI_API_KEY and ANTHROPIC_API_KEY unset.
- `grep -rnE 'api\.openai\.com|api\.anthropic\.com|OPENAI_API_KEY|ANTHROPIC_API_KEY|load_dotenv' src plugins .github` prints nothing.
- `PYTHONPATH=src python3 -m forgemyspec gate examples/budget-core` exits 0 and prints PASS for spec-lint, obligation-coverage, dafny-lint, contract-lock, verify, test, audit, mutation and python-boundary-tests.
- The gate exits non-zero, naming the failed stage, for each injected fault: an `assume` added to impl.dfy, an obligation tag removed, one byte changed in contract.dfy after locking, an uncovered must_include phrase, and dafny absent from PATH.
- The mutation stage reports total mutants, killed mutants and each survivor's file:line and operator, and meets policy mutation_min_kill_rate (default 0.9) on examples/budget-core.
- Every committed spec.yaml loads with yaml.safe_load and lints with zero errors.
- Every repository path referenced in README.md and CLAUDE.md exists in the tree.
- CI installs Dafny, runs the unit tests and runs the gate on examples/budget-core and on every changed bundle.

## Assumptions
- Primary distribution is: clone the repo and open it in Claude Code; skills call the harness with `PYTHONPATH=src python3 -m forgemyspec`. Claude Code plugin-marketplace packaging is a later version.
- Claude in the session is the only LLM; every harness step is deterministic and offline.
- Dafny 4.x is the formal toolchain, installed with `brew install dafny` locally and `dafny-lang/setup-dafny-action` in CI.
- Formalizable scope is the pure core logic (rules, invariants, state transitions); I/O, CLI parsing, files, network and databases are boundary code covered by Python tests.
- The contract lives in an abstract Dafny module (contract.dfy) and the implementation in a module that refines it (impl.dfy), so the implementation can be mutated without touching the contract.
- Obligation tags are plain Dafny comments of the form `// @obligation f1` placed directly above the clause or test they mark.
- experiments/ is historical benchmark evidence: its content is preserved and only YAML quoting is repaired.
- pydantic is removed as a dependency once the LLM draft-normalization path is deleted; PyYAML stays.

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- Abstract-module refinement (contract.dfy refined by impl.dfy) works in Dafny 4.11.0; the single-file fallback was not needed.
- The lock covers contract.dfy, tests.dfy, the spec's `formal` section and the spec version: everything the user approves.
- `dafny test` runs on the Python target (`--target py`): it is the shipping backend and about 4x faster than C#.
- Every Dafny stage runs in a scratch copy of the bundle, because `dafny test` writes build output into its working directory.

## Known Pitfalls
- Dafny does not verify files reached only through `include`; pass every file explicitly or a wrong impl "verifies".
- `dafny audit` exits 0 with findings; parse `completed with N findings`.
- `expect` in impl.dfy is an assumption to the verifier, and a bodiless contract function lets impl define the spec; neither is caught by `dafny audit`, so the Dafny lint bans both.
- In mutation, `=>` and generic `<`/`>` must be tokenized as non-operators, or mutants come out invalid.
