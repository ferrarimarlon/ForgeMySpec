# Acceptance Checklist (v0.4)

## Scope
- [x] Objective implemented: strict guards, risk box, kernel proven in Dafny, planted errors and `forgemyspec init`, all in English.
- [x] No unrequested features. Additions made to keep the measurement honest, each found while validating:
  - Planted errors must be rejected *by their `@target` obligation*. Stale planted errors were being rejected for an unrelated clause, so "6/6 rejected" measured nothing.
  - The kernel returns the *first* worst obligation. A surviving mutant showed that ties made the box's reason non-deterministic. The contract was strengthened before the user's approval.
  - The gate cache is versioned (`schema: 2`), so records from an older harness cannot break the box.
  - init removes earlier ForgeMySpec hook entries from settings.local.json, so the box is not shown twice.
- [x] Assumptions are explicit in spec.yaml.

## Success Criteria
- [x] init on a temporary git repo creates every component, merges settings and CLAUDE.md, keeps the old pre-commit, sets core.hooksPath; a second run changes nothing; --check exits 0, and 1 after a hook is removed (`test_init`).
- [x] The PreToolUse file guard denies the 13 protected or uncovered cases with a reason that names the next step, and objects to nothing in the 7 allowed cases (`test_hooks.FileGuardTests`).
- [x] The Bash guard denies 13 risky commands and allows 9 legitimate ones, including a heredoc with `>` inside Python code (`test_hooks.BashGuardTests`).
- [x] A crashing guard exits 2 (blocked), and init writes `onFailure: block` on the PreToolUse entry.
- [x] Stop blocks without a gate, shows the box with a current PASS gate, blocks after a file change, and releases with "WORK NOT VERIFIED" after 3 blocks (`test_hooks.StopHookTests`).
- [x] Per-obligation evidence: verify errors attributed through the cited contract clause, tests through their tags, surviving mutants through the containing method (`test_gate.EvidenceTests`).
- [x] Risk box: proven, fragile and leaking states rendered, every line at most 60 characters, token note read from the transcript (`test_hooks.RiskBoxTests`).
- [x] SessionStart and UserPromptSubmit inject each bundle's phase and next step (`test_hooks.StateTests`).
- [x] All harness output is in English (`test_messages`, which fails on any Portuguese word); lint negation works per language.
- [x] pre-commit rejected a commit with a broken impl.dfy and accepted it after the fix (end-to-end in a temporary repo).
- [ ] **Pending, user action:** this repository initialized with its own `init`. The order is: lock the kernel, lock budget-core, approve this bundle, then init.
- [ ] **Pending, user confirmation:** the risk box shows up in your VS Code session.
- [x] Kernel gate: every stage PASS, 25 proofs, mutants 30/30, planted errors 6/6 (temporary copy with a provisional lock; the real lock is the user's).
- [x] Planted-errors stage: budget-core 4/4. In the kernel, removing the two draft-implementation clauses makes `impl_allowed_without_lock` survive, and the gate names it. A mislabeled planted error fails as "rejected for the wrong reason".
- [x] The box shows each contract's strength (`strength: mutants 30/30 · planted errors 6/6`).
- [x] `kernel --check` detects a hand-edited `_kernel/` (exit 1) and is a CI step.
- [x] README has the "Trusted base" section.

## Required Evidence
- [x] Unit tests: 64 tests, OK, with API keys unset.
- [x] Guard pipe tests: decision tables in `tests/test_hooks.py`, plus 11 manual pipe cases run during development.
- [x] Stop hook PASS, FAIL and stop_hook_active cases.
- [x] Risk boxes in three states (test) and the real box for this repository (100% free before approvals; 34/34 met in the approval simulation).
- [x] Gate and lint output in English.
- [x] pre-commit rejection and acceptance.
- [ ] **Pending, after init:** an in-session PreToolUse deny on a real edit.
- [ ] **Pending:** the user's confirmation of the box in VS Code.
- [x] Full kernel gate report.
- [x] budget-core gate with planted errors, and the failure naming the surviving error.
- [x] `kernel --check` rejecting a hand-edited `_kernel/`.
- [ ] **Pending, after push:** the same checks in the GitHub CI log.

## Decision Rules Compliance
- [x] Undecidable guard input denies (exit 2), never allows.
- [x] Unreadable transcript shows "tokens unavailable".
- [x] At the repeat limit, the turn is released with "WORK NOT VERIFIED".
- [x] No bypass flag Claude can set: widening goes through config.yaml or scope.paths, both user-owned.
- [x] Every message comes from messages.py.
- [x] Kernel property issues were solved by strengthening the contract before approval, not by moving logic back into Python.
- [x] No planted error was deleted: stale ones were regenerated from the current impl.dfy, with the same targets.
