# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Make the ForgeMySpec flow impossible to skip inside Claude Code and visible on every prompt. The `forgemyspec init` command installs into any repository a copy of the harness, the skills and the agent, deterministic strict hooks, a git pre-commit gate and a CI gate. After every prompt a risk box shows which requirements are proven, only tested or leaking, where the project leaks, and how much of the code still leaves the LLM room to hallucinate. The decisions behind that trust (each obligation's color, each requirement's status, the guards' edit decision and coverage) come from a kernel proven in Dafny, and each contract's strength is also measured against planted errors.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] `forgemyspec init <temporary-git-repo>` creates .forgemyspec/harness, .forgemyspec/config.yaml, .claude/skills, .claude/agents, a merged .claude/settings.json with `agent: forgemyspec-default` and the hooks, a marked block in CLAUDE.md, .githooks/pre-commit with core.hooksPath set, and .github/workflows/forgemyspec.yml; a second run reports that nothing changed; `init --check` exits 0 on a fresh install and 1 after a hook entry is removed.
- [ ] Pipe tests of the PreToolUse guard return deny, with a reason that names the next step, for: an edit outside every approved bundle and the allow list; contract.dfy, tests.dfy, planted/ or the formal section after the lock; contract.lock; generated/; .forgemyspec/state; .claude/settings*.json; .forgemyspec/config.yaml. They object to nothing for impl.dfy and shell/ in a locked bundle and for allowed paths.
- [ ] Pipe tests of the Bash guard deny `forgemyspec lock`, `unlock`, `approve` and `init`, `git commit --no-verify`, and redirections, sed -i, tee, cp, mv or rm that hit a denied path, and allow read-only commands.
- [ ] A guard that raises an exception results in a blocked tool call (onFailure block checked in the hook entry and a pipe test that exits 2).
- [ ] The Stop hook returns decision block naming the bundle and the failed stages when a locked bundle has no PASS gate for its current content, allows stopping when it has one, and after the stop_hook_active continuations allows stopping with a systemMessage saying the work is not verified.
- [ ] The gate records evidence per obligation: verification errors attributed to obligations through the contract clause they cite, Dafny and Python tests attributed through their tags, and surviving mutants attributed to the obligations of the method that contains them.
- [ ] After every turn the Stop hook shows a multi-line risk box, no line longer than 60 characters, with: requirements met out of total; one line per must_include requirement with PROVEN, FRAGILE or LEAKING and the reason; the room-to-hallucinate split (proven, examples only, free) in lines and percent with the change since the previous turn; each leak with file:line; the items only the user guarantees (contract and assumptions, and when they approved them); and a note with the turn's LLM tokens or 'tokens unavailable'.
- [ ] SessionStart and UserPromptSubmit inject a state summary listing each bundle with its phase (draft, approved, gate PASS or FAIL) and the next required step.
- [ ] Every harness message is in English, and the lint detects negation in hypotheses written in English or Portuguese without flagging the Portuguese contraction 'no'.
- [ ] The pre-commit hook runs the gate on bundles with staged changes and rejects the commit when one fails; the CI workflow runs the same check.
- [ ] This repository is initialized with its own `init` in strict mode, and all work after that point goes through the guards.
- [ ] The risk box appears in the user's Claude Code session in VS Code after a real turn, confirmed by the user.
- [ ] `gate forgemyspec-bundle/kernel` passes every stage, including mutation and planted errors, with these properties: Proven requires zero failures, zero surviving mutants and passing tests; a met requirement requires an approved bundle, a current gate and no leaking obligation; an edit to a protected path is never allowed; an implementation is only allowed with a locked contract; coverage with no missing items is equivalent to every phrase and hypothesis being covered.
- [ ] A `planted-errors` gate stage requires, by default, at least 3 implementations in planted/ and that all of them are rejected by dafny verify or dafny test; examples/budget-core passes with its planted errors, and the gate fails naming the surviving error when the clauses that caught it are removed from the contract.
- [ ] The risk box shows, for each formal bundle, the contract's strength: killed mutants out of valid ones and planted errors rejected out of the total.
- [ ] CI fails when src/forgemyspec/_kernel/ diverges from a fresh translation of the kernel.
- [ ] The README has a 'Trusted base' section listing what is proven, what is only tested and what remains trust (Dafny and Z3, Python, git and the user's approval).
- [ ] `forgemyspec request-approval lock:<bundle> approve:<bundle> unlock:<bundle> init:.` prints one code bound to the content hash of every item; the code is accepted only from a human-origin transcript message recorded after the request, for unchanged content, once per item; any other case is refused with the reason (no human approval, content changed, already used).
- [ ] From Claude's Bash tool, `lock`, `approve`, `unlock` and `init` run only with a valid chat approval and are denied otherwise, both by the Bash guard and by the command itself; the lock records approved_via (chat or terminal), the code and the time, and the box shows them.

## Required Evidence
- [ ] Unit test output for init (fresh install, idempotent second run, merge with existing settings and CLAUDE.md, --check drift).
- [ ] Pipe test output for every guard decision listed in the success criteria, with the JSON each hook printed.
- [ ] Stop hook pipe test output for the PASS, FAIL and stop_hook_active cases.
- [ ] Risk boxes rendered for budget-core in three states: all proven, one surviving mutant (FRAGILE) and a failing verify (LEAKING).
- [ ] Gate and lint output in English, and the lint flagging a hypothesis that contains 'not'.
- [ ] A commit attempt rejected by pre-commit with a failing bundle, and accepted after the fix.
- [ ] In-session proof that a PreToolUse deny fired on a real edit in this repository after init.
- [ ] The user's confirmation that the risk box appears in their VS Code session.
- [ ] Full gate report for forgemyspec-bundle/kernel, with mutation and planted errors.
- [ ] Gate output for examples/budget-core with the planted errors rejected, and the failure naming the surviving error after clauses are removed.
- [ ] CI output (or the same command locally) rejecting a hand-edited _kernel/.
- [ ] A chat approval flow run end to end: request, refused without the code, refused after a content change, accepted with the code, refused on reuse.

## Decision Rules Compliance
- [ ] If a guard cannot decide (unreadable input, unknown tool), deny in strict mode and state the cause; never allow by default.
- [ ] If the transcript's token usage cannot be read, show 'tokens unavailable' in the box; never estimate tokens.
- [ ] If the Stop repeat limit is reached with the gate failing, release the turn with a systemMessage saying the work is not verified; never present it as done.
- [ ] If a guard blocks legitimate work, widen the rule through config.yaml or a bundle's scope.paths with the user's approval; never add a bypass flag Claude can turn on.
- [ ] If a hook would exceed its time budget, cache the expensive part (bundle discovery, hashes) in .forgemyspec/state instead of dropping the check.
- [ ] If a message text is not in the messages module, the test fails; never let text outside the catalog reach the user.
- [ ] If a kernel property cannot be proven as written, stop and amend with the user; never move the decision back into unproven Python.
- [ ] If a planted error survives, strengthen the contract or the tests with the user's new approval; never delete the planted error.
