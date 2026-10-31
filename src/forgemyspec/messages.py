"""Every text the harness shows the user or Claude.

No other module writes user-facing sentences: they import from here. That keeps wording in one place and
lets the messages test check that nothing outside the catalog reaches the user.
Output of external tools (Dafny itself) is passed through as is, marked with the `dafny│` prefix.
"""

from __future__ import annotations

TOOL_PREFIX = "dafny│ "

# ---------------------------------------------------------------------------
# Spec lint (key = code, with a /variant suffix when a code has more than one sentence)
# ---------------------------------------------------------------------------

LINT = {
    "LINT-STRUCT-000": "Spec must be a YAML mapping; found {found}",
    "LINT-STRUCT-001": "Missing required field: {field}",
    "LINT-STRUCT-002": "Invalid type for {field}: expected {type}",
    "LINT-STRUCT-003": "execution_mode is '{mode}'; expected 'critical' for high-stakes specs",
    "LINT-CTX-002": "context.system must be a non-empty string",
    "LINT-CTX-003": "context.assumptions must be a list",
    "LINT-MIN-001": "Field '{field}' must have at least {minimum} item(s); received {received}",
    "LINT-HY-001": "Hypothesis entry must be an object",
    "LINT-HY-002": "Hypothesis id must be a non-empty string",
    "LINT-HY-003": "Hypothesis ids must be unique",
    "LINT-HY-004": "Hypothesis description must be non-empty",
    "LINT-HY-005": "Hypothesis confidence must be numeric",
    "LINT-HY-006": "Hypothesis confidence must be between 0 and 1",
    "LINT-HY-007": "Hypothesis appears to describe what will NOT be built; hypotheses must be affirmative and testable",
    "LINT-ACT-001": "Action entry must be an object",
    "LINT-ACT-002": "Action id must be a non-empty string",
    "LINT-ACT-003": "Action ids must be unique",
    "LINT-ACT-004": "Action type must be a non-empty string",
    "LINT-ACT-005": "Action type '{type}' is outside policy allowed_action_types",
    "LINT-ACT-006": "Action description must be non-empty",
    "LINT-ACT-007": "Action requires_confirmation must be a boolean",
    "LINT-ACT-008": "Action supports must be a non-empty list of hypothesis ids",
    "LINT-ACT-009": "Action supports entries must be non-empty strings",
    "LINT-TR-001": "Action references unknown hypothesis id: {id}",
    "LINT-TR-002": "Hypothesis is not linked by any action: {id}",
    "LINT-TR-003": "'{type}' action supports all {total} hypotheses ({ids}); each non-validation action should target only the hypotheses it directly advances",
    "LINT-META-001": "metadata.{field} must be a non-empty string",
    "LINT-EV-001": "Evidence item describes an artifact, not an observable output; prefer runnable examples, test results, or concrete outputs",
    "LINT-DUP-001": "Field '{field}' contains duplicate or near-duplicate entries",
    "LINT-FORMAL-000": "Missing 'formal' section required by the gate",
    "LINT-FORMAL-001/mapping": "'formal' must be a mapping",
    "LINT-FORMAL-001/module": "formal.module must be a Dafny identifier",
    "LINT-FORMAL-001/list": "formal.obligations must be a non-empty list",
    "LINT-FORMAL-002/object": "Obligation entry must be an object",
    "LINT-FORMAL-002/format": "Obligation id must match [a-z][a-z0-9_]*",
    "LINT-FORMAL-002/duplicate": "Obligation id is not unique: {id}",
    "LINT-FORMAL-003": "Obligation kind must be one of {kinds}",
    "LINT-FORMAL-004/empty": "Obligation must list the hypotheses it covers",
    "LINT-FORMAL-004/unknown": "Obligation references unknown hypothesis id: {id}",
    "LINT-FORMAL-005/list": "Obligation must_include must be a list",
    "LINT-FORMAL-005/phrase": "Obligation must_include entry is not an exact scope_contract.must_include phrase: {phrase!r}",
    "LINT-FORMAL-006": "Boundary obligation must name its Python test id",
    "LINT-FORMAL-007": "Hypothesis is not covered by any formal obligation: {id}",
    "LINT-FORMAL-008": "must_include phrase is not covered by any formal obligation: {phrase!r}",
    "LINT-FORMAL-009": "Obligation statement must be non-empty",
}

LINT_REPORT_SCORE = "Lint score: {score}/100"
LINT_REPORT_ERRORS = "Errors: {n}"
LINT_REPORT_WARNINGS = "Warnings: {n}"
LINT_REPORT_CLEAN = "No issues found."
LINT_REPORT_ISSUES = "Issues:"
SEVERITY = {"error": "ERROR", "warning": "WARNING"}
EMPTY_FILE = "empty file"

# ---------------------------------------------------------------------------
# Dafny lint
# ---------------------------------------------------------------------------

DFY = {
    "LINT-DFY-000": "Missing required file: {file}",
    "LINT-DFY-001": "Banned construct: {construct}",
    "LINT-DFY-003": "contract.dfy must declare `abstract module {module}`",
    "LINT-DFY-004": "impl.dfy must declare a non-abstract `module ... refines {module}`",
    "LINT-DFY-005": "Obligation '{id}' has no `// @obligation` tag directly above a contract clause or member",
    "LINT-DFY-006": "Obligation '{id}' has no `// @obligation` tag directly above a {{:test}} method",
    "LINT-DFY-007": "Tag references unknown obligation id: {id}",
    "LINT-DFY-009": "Contract method '{name}' has a body; implementations belong in impl.dfy",
    "LINT-DFY-010": "Contract {kind} '{name}' has no body; impl.dfy would get to define the specification",
    "LINT-DFY-011": "Contract method '{name}' has no ensures clause, so it constrains nothing",
    "LINT-DFY-012": "Planted error {file} does not say which obligation it attacks; put `// @target <id>` at the top",
    "LINT-DFY-013": "Planted error {file} attacks an obligation that does not exist: {id}",
}

BANNED_CONSTRUCTS = {
    "assume": "`assume` statement",
    "axiom": "`{:axiom}` attribute",
    "verify_false": "`{:verify false}` attribute",
    "extern": "`{:extern}` attribute",
    "only": "`{:only}` attribute",
    "decreases_star": "`decreases *` (permits non-termination)",
    "requires_false": "`requires false` (vacuous precondition)",
    "ensures_true": "`ensures true` (vacuous postcondition)",
    "expect": "`expect` statement (the verifier assumes it; use only in tests.dfy)",
}

# ---------------------------------------------------------------------------
# Locks
# ---------------------------------------------------------------------------

LOCK_MISSING = "contract.lock is missing; the contract has not been approved and locked"
LOCK_FILE_MISSING = "{file} is missing, so the lock cannot be checked"
LOCK_INVALID = "{file} is not a valid YAML mapping"
LOCK_CHANGED = "{item} changed since the contract was approved; approve again and run `lock`"
LOCK_ITEMS = {
    "lock_version": "the lock format version",
    "spec_version": "the spec version",
    "contract_sha256": "contract.dfy",
    "tests_sha256": "tests.dfy",
    "planted_sha256": "the planted/ folder (planted errors)",
    "formal_sha256": "the spec.yaml formal section",
}
SPEC_LOCK_MISSING = "spec.lock is missing; the spec has not been approved yet"
SPEC_CHANGED_AFTER_APPROVAL = "spec.yaml changed since it was approved; approve again with `approve`"

# ---------------------------------------------------------------------------
# Policy and tools
# ---------------------------------------------------------------------------

POLICY_ERROR = "Policy configuration error: {error}"
POLICY = {
    "min_items": "'min_items' must be a mapping",
    "min_items_values": "'min_items' keys must be strings and values must be non-negative integers",
    "allowed_action_types": "'allowed_action_types' must be a list",
    "require_action_support_links": "'require_action_support_links' must be a boolean",
    "required_metadata_fields": "'required_metadata_fields' must be a list",
    "scope_contract_field": "'scope_contract_field' must be a non-empty string",
    "kill_rate": "'mutation_min_kill_rate' must be a number between 0 and 1",
    "dafny_min_version": "'dafny_min_version' must be a dotted version string such as '4.0'",
    "integer": "'{field}' must be an integer",
    "minimum": "'{field}' must be >= {minimum}",
    "yaml": "Invalid YAML policy file: {path}",
}
DAFNY_INSTALL = "Install Dafny 4.x: `brew install dafny` (macOS) or see https://github.com/dafny-lang/dafny/releases"
DAFNY_MISSING = "`dafny` was not found on PATH. " + DAFNY_INSTALL
DAFNY_TOO_OLD = "Dafny {version} is older than the required {minimum}. " + DAFNY_INSTALL
DAFNY_VERSION_UNREADABLE = "Could not read the Dafny version from `{dafny} --version`: {output}"
TIMED_OUT = "[timed out after {seconds}s]"

# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

STAGES = {
    "spec-lint": "spec lint",
    "obligation-coverage": "obligation coverage",
    "dafny-lint": "Dafny lint",
    "contract-lock": "contract lock",
    "spec-lock": "spec lock",
    "toolchain": "toolchain",
    "verify": "verification (dafny verify)",
    "test": "Dafny tests",
    "audit": "audit (dafny audit)",
    "translate": "translation to Python",
    "python-boundary-tests": "Python boundary tests",
    "verify-command": "verify command",
    "mutation": "mutation",
    "planted-errors": "planted errors",
}
STATUS = {"PASS": "PASS", "FAIL": "FAIL", "BLOCKED": "BLOCKED"}

GATE_TITLE = "ForgeMySpec gate: {bundle}"
GATE_RESULT = "RESULT: {result}"
GATE_SPEC_MISSING = "Missing {file}"
GATE_YAML_INVALID = "YAML parse error: {error}"
GATE_SCORE = "score {score}/100 (minimum {minimum})"
GATE_BLOCKED_BY = "blocked by: {stages}"
GATE_BLOCKED_EARLIER = "blocked by earlier failures"
GATE_FINDINGS = "{n} findings"
GATE_WROTE = "wrote {path}"
GATE_NO_TESTS_PY = "tests_py/ is missing; the translated core needs Python tests"
GATE_NO_TESTS = "no tests were discovered in {folder}"
GATE_TESTS_SUMMARY = "{total} tests, {failed} failed, {skipped} skipped"
GATE_TEST_FAILED = "failed: {id}"
GATE_BOUNDARY_MISSING = "boundary obligation {obligation}: test {test!r} was not found"
GATE_BOUNDARY_SKIPPED = "boundary obligation {obligation}: test {test!r} was skipped"
GATE_MUTATION_SUMMARY = (
    "{candidates} candidate mutants, {run} run, {killed}/{valid} killed ({rate}), "
    "{invalid} invalid; minimum {minimum}"
)
GATE_MUTANT_ALIVE = "{status}: impl.dfy:{line}:{column} `{original}` -> `{replacement}`"
GATE_MUTANT_STATUS = {"survived": "survived", "timeout": "timed out"}
GATE_MUTANT_EQUIVALENT = "suppressed as equivalent: impl.dfy:{line} - {reason}"
GATE_MUTANT_NO_REASON = "NO REASON GIVEN"
GATE_NO_MUTANTS = "no valid mutants were generated, so the contract's strength is unmeasured"
GATE_TOOLCHAIN = "dafny {version} ({path})"
GATE_NO_VERIFICATION = "the spec-only bundle declares neither scope.tests nor scope.verify_command; nothing checks the code"
GATE_COMMAND = "command: {command} (exit {code})"
GATE_PLANTED_SUMMARY = "{rejected}/{total} planted errors rejected (minimum {minimum})"
GATE_PLANTED_SURVIVED = "survived: {file} (attacks {target}) passed verify and the tests"
GATE_PLANTED_INVALID = "invalid: {file} does not compile (exit {code}); a planted error must be valid code"
GATE_PLANTED_WRONG_REASON = (
    "rejected for the wrong reason: {file} attacks {target}, but verification failed on {by}; "
    "regenerate it from the current impl.dfy"
)
GATE_PLANTED_TOO_FEW = "only {n} planted error(s) in planted/; the minimum is {minimum}"

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

CLI_DESCRIPTION = "ForgeMySpec harness: spec lint, approval and locks, the formal gate, guards and installation."
CLI_HELP = {
    "lint": "Lint a spec.yaml.",
    "formal": "Require the formal section (as the gate does).",
    "package": "Lint a spec.yaml and write the bundle files next to it.",
    "output-dir": "Defaults to the spec's directory.",
    "lock": "Record the user-approved contract.dfy, tests.dfy, planted/ and formal section (needs the user's approval).",
    "check-lock": "Run the lock checks without writing anything.",
    "approve": "Approve a spec-only bundle by writing spec.lock (needs the user's approval).",
    "unlock": "Remove a bundle's lock to allow an amendment (needs the user's approval).",
    "request-approval": "Ask the user to approve actions in the chat: prints a code the user types back.",
    "items": "Items as action:target, for example lock:examples/budget-core or init:.",
    "gate": "Run every gate stage on a bundle.",
    "all": "Run the gate on every approved bundle in the project.",
    "hook": "Entry point for the Claude Code hooks (internal).",
    "risk": "Print the project's risk box.",
    "json": "Print the live panel's data as JSON instead of the box.",
    "board": "Print the conversation board: each request as a requirement, with status bars.",
    "detail": "Print one requirement in full (for example R11), or `start R11` to mark the requirement being worked on.",
    "fast": "In-session tier: skip mutation and planted errors; a spec-only bundle runs only its obligations' tests.",
    "kernel": "Generate src/forgemyspec/_kernel from the Dafny kernel, or compare with --check.",
    "init": "Install ForgeMySpec into a repository (needs the user's approval).",
    "suspend": "Turn the guards off in a repository, keeping bundles and locks (needs the user's approval).",
    "check-init": "Only compare the installation; exit 1 when something differs.",
    "python": "Python interpreter the hooks will use.",
}
CLI_FILE_UNREADABLE = "Cannot read {file}: {error}"
CLI_BUNDLE_WRITTEN = "Bundle written to {path}"
CLI_LOCK_REFUSED = "Refusing to lock: fix the static checks first."
CLI_LOCK_CHECKED = "Lock checks passed; nothing was written."
CLI_LOCK_WRITTEN = "Locked {path} (spec version {version})"
CLI_APPROVE_FORMAL = "{bundle} has a Dafny contract; use `lock`, not `approve`."
CLI_APPROVE_WRITTEN = "Approved {path} (spec version {version})"
CLI_UNLOCK_DONE = "Lock removed: {path}. After the amendment, approve again."
CLI_UNLOCK_NO_LOCK = "{bundle} has no lock."
CLI_NO_BUNDLES = "No approved bundles found."
CLI_NOT_A_BUNDLE = "{path} has no spec.yaml."
SUSPEND_CHANGED = "removed  {item}"
SUSPEND_DONE = "ForgeMySpec guards suspended. Bundles, locks and the harness copy are unchanged; `init` turns the guards back on."
SUSPEND_NOTHING = "Nothing to suspend: no ForgeMySpec hooks are installed."
APPROVAL_BAD_ITEM = "Not an approvable item: {item}. Use action:target with action one of {actions}."
APPROVAL_UNREADABLE = "Cannot compute what {item} covers: {error}"
APPROVAL_REQUESTED = "Approval requested. Code: {code}"
APPROVAL_ITEM = "  {action} {target}  (content {sha})"
APPROVAL_ASK = "Show the user exactly what each item approves, then ask them to type the code {code} in the chat. Nothing else counts as approval."
APPROVAL_REFUSED = {
    "no-typed-code": "Not approved: no message typed by the user contains the code of a request for `{action} {target}`. Run `request-approval {action}:{target}` and ask the user to type the code.",
    "content-changed": "Not approved: `{action} {target}` changed after the user approved it (code {code}). Request a new approval.",
    "already-used": "Not approved: the approval {code} for `{action} {target}` was already used. Request a new approval.",
}
APPROVAL_USED = "Approved by the user in the chat (code {code})."
APPROVAL_TERMINAL = "Approved by the user in their terminal."
KERNEL_DIFFERS = "differs: _kernel/{item}"
KERNEL_MATCHES = "_kernel/ matches a fresh translation."
KERNEL_DIVERGED = "_kernel/ differs from the translation; run `python -m forgemyspec kernel` and commit the result."
KERNEL_GENERATED = "Generated {path}"

# ---------------------------------------------------------------------------
# Guards (hooks)
# ---------------------------------------------------------------------------

GUARD_NEXT = "\nNext step: {step}"
GUARD_PROTECTED = (
    "Blocked by ForgeMySpec: {path} is protected (guard configuration, harness state, lock or generated code). "
    "Only the user changes it."
)
GUARD_OUTSIDE_SPEC = "Blocked by ForgeMySpec: {path} is not covered by any approved spec."
GUARD_OUTSIDE_SPEC_STEP = (
    "create or amend a spec with /forgemyspec that covers this path (scope.paths) and ask the user to approve it; "
    "or ask them to add the path to allow_paths in .forgemyspec/config.yaml"
)
GUARD_NOT_APPROVED = "Blocked by ForgeMySpec: bundle {bundle}, which covers {path}, has not been approved yet."
GUARD_NOT_APPROVED_STEP = "show the spec (and the contract, if any) to the user and ask for approval: `request-approval` prints a code; the user types it in the chat, then run {command}"
GUARD_CONTRACT_LOCKED = "Blocked by ForgeMySpec: {path} is locked; the user approved this version."
GUARD_CONTRACT_LOCKED_STEP = "use /forgemyspec-amend to propose the change; with the user's approval (`request-approval` prints a code; the user types it in the chat) run `{command}` before the edit, and ask for approval again afterwards"
GUARD_FORMAL_LOCKED = "Blocked by ForgeMySpec: this edit changes the formal section or the version of {path}, which are locked."
GUARD_SPEC_LOCKED = "Blocked by ForgeMySpec: {path} was approved by the user and is locked."
GUARD_IMPL_WITHOUT_LOCK = "Blocked by ForgeMySpec: {path} is implementation, but the contract of bundle {bundle} has not been approved yet."
GUARD_IMPL_WITHOUT_LOCK_STEP = "finish /forgemyspec-formalize and ask for approval: `request-approval` prints a code; the user types it in the chat, then run {command}"
GUARD_LOCK_INVALID = "Blocked by ForgeMySpec: the lock of bundle {bundle} does not match; the contract or the spec changed without new approval."
GUARD_LOCK_INVALID_STEP = "ask the user to review the change and approve again (`request-approval` prints a code; the user types it in the chat), then run {command}"
GUARD_SPEC_INVALID = "Blocked by ForgeMySpec: the spec.yaml of {bundle} cannot be read ({error})."
GUARD_SPEC_INVALID_STEP = "fix the bundle's spec.yaml"
GUARD_UNDECIDABLE = "Blocked by ForgeMySpec (strict mode): could not decide on this action ({cause})."
GUARD_HUMAN_COMMAND = "Blocked by ForgeMySpec: `{command}` is an approval or an installation change and needs the user's approval. {reason}"
GUARD_HUMAN_COMMAND_STEP = "run `{command}`, show the user what each item approves and ask them to type the code in the chat"
GUARD_NO_VERIFY = "Blocked by ForgeMySpec: skipping the git hooks (--no-verify, -n or core.hooksPath) turns off the pre-commit gate."
GUARD_NO_VERIFY_STEP = "commit without skipping the hooks; if the gate fails, fix what it reports"
GUARD_SHELL_WRITE = "Blocked by ForgeMySpec: this shell command writes to {path}. {reason}"

# ---------------------------------------------------------------------------
# Stop and injected state
# ---------------------------------------------------------------------------

STOP_BLOCK = (
    "ForgeMySpec will not let you finish yet: bundle {bundle} is approved but has no passing gate for its current "
    "content ({reason}). Run `{command}` and fix whatever fails."
)
STOP_REASON_NO_GATE = "the gate never ran"
STOP_REASON_STALE = "files changed since the last run"
STOP_REASON_FAILED = "failed at: {stages}"
STOP_RELEASED_UNVERIFIED = "⚠ WORK NOT VERIFIED: the gate is still failing for {bundles}. None of this is done."
STOP_BOX_ERROR = "ForgeMySpec: could not build the risk box ({error})."

STATE_TITLE = "ForgeMySpec ({mode} mode). Bundle state:"
STATE_NONE = "ForgeMySpec ({mode} mode): no bundles in the project. Before writing code, run /forgemyspec."
STATE_LINE = "- {bundle} [{kind}]: {phase}; next step: {step}"
BUNDLE_KIND = {True: "Dafny contract", False: "spec-only"}
PHASES = {
    "draft": "draft spec, not approved",
    "locked": "approved",
    "lock-invalid": "lock does not match",
    "spec-invalid": "spec unreadable",
}
GATE_STATE = {"pass": "gate PASS", "fail": "gate FAIL", "stale": "gate stale", "none": "gate never ran"}
STEPS = {
    "draft": "finish the spec (and the contract, if formal), ask for approval with `request-approval` (the user types the code in the chat), then run `{command}`",
    "locked-ok": "nothing pending; changes go through the guards",
    "locked-pending": "run `{command}` until it passes",
    "lock-invalid": "show the user the change and ask for approval again with `request-approval` (the user types the code in the chat), then run `{command}`",
    "spec-invalid": "fix the spec.yaml",
}
STATE_RULES = (
    "Rules: edits only in paths covered by an approved bundle; contract, locks, config and generated/ belong to the "
    "user; lock, approve, unlock and init need the user's approval: a `request-approval` code the user types in the chat, never Claude's reading of plain words. "
    "Board: every user request is a requirement in forgemyspec-board.yaml (the user's words, checkable steps); "
    "the reply is the output of `forgemyspec board`; explain only when asked (`board R<n>`)."
)

# ---------------------------------------------------------------------------
# Risk box
# ---------------------------------------------------------------------------

BOX_TITLE = "ForgeMySpec · project risk"
BOX_REQUIREMENTS = "REQUIREMENTS: {met} of {total} met"
BOX_NO_REQUIREMENTS = "REQUIREMENTS: no approved bundles yet"
BOX_SAME_REASON = "requirements, all for the same reason:"
BOX_STATUS = {"proven": "🟢", "fragile": "🟡", "leaking": "🔴"}
BOX_ROOM = "ROOM FOR THE LLM TO HALLUCINATE"
BOX_BANDS = {"proven": "proven", "examples": "examples only", "free": "free"}
BOX_LINES = "lines"
BOX_CHANGE = "vs. previous prompt: {change}"
BOX_NO_CHANGE = "vs. previous prompt: no change"
BOX_FIRST = "first measurement"
BOX_PROVEN_CHANGE = "proven {change}"
BOX_TEXT = "unverified text (docs, config): {n} lines"
BOX_LEAKS = "WHERE IT LEAKS"
BOX_NO_LEAKS = "no leaks found"
BOX_HUMAN = "WHAT ONLY YOU GUARANTEE"
BOX_HUMAN_CONTRACT = "does the contract of {bundle} say what you meant?"
BOX_HUMAN_SPEC = "does the spec of {bundle} say what you meant?"
BOX_HUMAN_APPROVED = "approved by you on {when}"
BOX_HUMAN_APPROVED_CHAT = "approved by you in chat on {when} ({code})"
BOX_HUMAN_PENDING = "not approved by you yet"
BOX_HUMAN_LOCK_STALE = "the lock no longer matches; approve again"
BOX_HUMAN_ASSUMPTIONS = "{n} spec assumptions, approved in the same lock"
BOX_PROMPT = "THIS PROMPT"
BOX_PROMPT_BLOCKS = "{n} actions blocked by the guards"
BOX_PROMPT_GATES = "gate ran {n}×"
BOX_TOKENS = "cost: {input} input tokens ({cache} cached) · {output} output"
BOX_TOKENS_UNAVAILABLE = "cost: tokens unavailable"
BOX_MORE = "  … and {n} more"
BOX_STRENGTH = "strength: mutants {killed}/{valid} · planted errors {rejected}/{total}"

REASONS = {
    "proof": "proven by Dafny",
    "boundary": "tested with examples only",
    "mutant": "proven, but {n} mutant(s) survived",
    "blocked": "proven, but the tests did not run (the gate stopped earlier)",
    "uncovered": "LEAKING: no obligation covers it",
    "failed": "LEAKING: {stage} failed",
    "stale": "LEAKING: changed since the last gate",
    "no-gate": "LEAKING: the gate never ran",
    "not-approved": "LEAKING: bundle not approved yet",
    "lock-invalid": "LEAKING: the lock does not match (approve again)",
    "spec-invalid": "LEAKING: the spec.yaml cannot be read",
}
LEAK_MUTANT = "{place}  `{original}`→`{replacement}` passes without being caught"
LEAK_VERIFY = "{place}  breaks the requirement \"{requirement}\""
LEAK_TEST = "{test} failed"
LEAK_PLANTED = "{place}: planted error passes without being caught"
LEAK_FREE = "{file}: {n} lines with no spec"

# ---------------------------------------------------------------------------
# Installation (init) and pre-commit
# ---------------------------------------------------------------------------

INIT_NOT_GIT = "{path} is not a git repository; run `git init` first."
INIT_NO_YAML = "Python {python} does not have PyYAML; install it with `{python} -m pip install pyyaml` and run again."
INIT_CREATED = "created     {path}"
INIT_UPDATED = "updated     {path}"
INIT_UP_TO_DATE = "Installation is up to date; nothing changed."
INIT_DONE = "ForgeMySpec installed in strict mode. Open a new Claude Code session (or /hooks) to activate the guards."
INIT_BRANCH_PROTECTION = "Manual step: protect the main branch on GitHub by requiring the 'ForgeMySpec gate' check."
INIT_CHECK_OK = "Installation matches."
INIT_CHECK_DIFFERS = "Installation differs in:"
PRE_COMMIT_FAILED = "ForgeMySpec: commit refused; the gate failed for {bundles}."
PRE_COMMIT_OK = "ForgeMySpec: gate passed for {n} bundle(s)."

# ---------------------------------------------------------------------------
# Bundle file templates (package)
# ---------------------------------------------------------------------------

TEMPLATE_CLAUDE = {
    "title": "# CLAUDE.md",
    "role_title": "## Role",
    "role": "You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.",
    "memory_title": "## Persistent Memory Policy",
    "memory": [
        "This file is project memory and should persist across sessions.",
        "Update only stable project knowledge (decisions, conventions, pitfalls).",
        "Do not store ephemeral logs or temporary debugging notes here.",
    ],
    "snapshot_title": "## Current Spec Snapshot",
    "spec_title": "Title: {title}",
    "objective": "Objective: {objective}",
    "guardrails_title": "## Non-Negotiable Guardrails",
    "rules_title": "## Decision Rules",
    "success_title": "## Success Criteria",
    "assumptions_title": "## Assumptions",
    "protocol_title": "## Implementation Protocol",
    "protocol": [
        "1. Read `spec.yaml` first and implement only traceable scope.",
        "2. If details are missing, document explicit assumptions before coding.",
        "3. Do not add features, frameworks, or layers outside the spec objective.",
        "4. Verify all success criteria with concrete evidence (tests, commands, outputs).",
        "5. Report residual risks and unresolved assumptions in the final summary.",
    ],
    "decisions_title": "## Decision Log",
    "decisions": "- (record stable architecture or policy decisions here)",
    "pitfalls_title": "## Known Pitfalls",
    "pitfalls": "- (record recurring implementation failure modes here)",
}
TEMPLATE_COMMAND_FORMAL = (
    "Implement strictly from `./spec.yaml`, `./CLAUDE.md` and the locked `./contract.dfy` + `./tests.dfy`.\n\n"
    "Execution steps:\n"
    "1. Confirm `contract.lock` exists. If it does not, run /forgemyspec-formalize and get the user's approval first.\n"
    "2. Never edit `contract.dfy`, `tests.dfy`, `planted/` or the spec's `formal` section; changes go through /forgemyspec-amend.\n"
    "3. Write `impl.dfy` as a module refining the contract, then `shell/` and `tests_py/` for boundary obligations.\n"
    "4. From the repository root, run `python3 -m forgemyspec gate <path-to-this-bundle>` until every stage passes.\n"
    "5. Return a final report with: changed files, the full gate report, assumptions made, and residual risks.\n"
)
TEMPLATE_COMMAND = (
    "Implement strictly from `./spec.yaml` and `./CLAUDE.md`.\n\n"
    "Execution steps:\n"
    "1. Parse objective, constraints, success criteria, decision rules, and actions from spec.\n"
    "2. Produce a short implementation plan mapped to action IDs.\n"
    "3. Implement only in-scope changes. Do not add unrequested features.\n"
    "4. Run validations/tests to satisfy success criteria.\n"
    "5. Return a final report with: changed files, evidence, assumptions made, and residual risks.\n"
)
TEMPLATE_CHECKLIST = {
    "title": "# Acceptance Checklist",
    "scope_title": "## Scope",
    "objective": "- [ ] Objective implemented exactly: {objective}",
    "no_extras": "- [ ] No unrequested features were introduced",
    "assumptions": "- [ ] All assumptions are explicit and justified",
    "success_title": "## Success Criteria",
    "evidence_title": "## Required Evidence",
    "rules_title": "## Decision Rules Compliance",
}
TEMPLATE_EVAL_PURPOSE = "Manual eval seeds to detect scope drift in Claude implementations"

# ---------------------------------------------------------------------------
# Conversation board (`board`)
# ---------------------------------------------------------------------------

BOARD_TITLE = "ForgeMySpec · {n} requirements"
BOARD_ROW = "{label:<9} {bar} {value}"
BOARD_DONE_LABEL = "done"
BOARD_STATUS = {"done": "done", "doing": "doing", "open": "open", "blocked": "blocked"}
BOARD_ICON = {"done": "✅", "doing": "🔵", "open": "⚪", "blocked": "🔴"}
BOARD_HARNESS = "harness"
BOARD_HARNESS_VALUE = "{p}%  {runs} runs + {checks} checks"
BOARD_MODEL = "model"
BOARD_MODEL_VALUE = "{p}%  {writes} writes · {tokens} tokens"
BOARD_CHANGED = "changed:"
BOARD_ACTIVE = "{icon} {id} {bar} {p:>3}%  {effort}  {title}"
BOARD_EFFORT = "H{h:>3}% M{m:>3}%"
BOARD_EFFORT_NONE = "H   –  M   – "
BOARD_EFFORT_LINE = "  effort {effort}  (H = harness runs, M = model writes)"
BOARD_CONTRACT = "  contract:"
BOARD_PROGRESS = "  progress {bar} {p}%"
BOARD_STEP = "  {mark} {text}"
BOARD_ITEM = "{icon} {id} {title}"
BOARD_FIELD = "  {label}: {text}"
BOARD_FIELDS = {"quote": "you said", "done": "done", "evidence": "evidence", "harness": "harness", "next": "next"}
BOARD_UNKNOWN = "No requirement {id} on the board."
