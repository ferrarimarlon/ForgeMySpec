# ForgeMySpec

[![Tests](https://github.com/ferrarimarlon/forgemyspec/actions/workflows/tests.yml/badge.svg)](https://github.com/ferrarimarlon/forgemyspec/actions/workflows/tests.yml)

**You say what you want. Claude writes it down as a spec. You approve it. A machine, not the AI, decides when it is done.**

ForgeMySpec is a harness for **Claude Code**. Claude writes the spec, the tests, and the code. When the logic is
critical, Claude also writes a Dafny contract and a proven core. A deterministic harness checks every step:
lint, coverage, locks, tests, proofs, mutants and planted errors. The harness uses no LLM and no network.

```
   YOU                    CLAUDE                         HARNESS (deterministic)
    │
    │  "build X"  ───────▶  spec.yaml  ───────────────▶  lint + coverage
    │                          │
    │  ◀── code: K7Q2XF ───────┘   request-approval
    │  types K7Q2XF  ─────────────────────────────────▶  approve / lock (SHA-256)
    │                          │
    │                       code + tests  ────────────▶  gate: PASS / FAIL
    │                          │
    │  ◀──────── the board: every request, every step, verified or only claimed
```

**Three ideas, everything else follows:**

| | |
|---|---|
| 📜 **Spec before code** | Every request becomes a `spec.yaml`. Every requirement in it maps to a named test or a Dafny proof. |
| 🔐 **You approve, with a code** | Approval is a 6-character code bound to the exact content. A plain "yes" does not count, and the AI cannot approve for you. |
| ✔ **Done means checked** | "Done" is a passing gate. The board shows ✔ only for steps a harness check verified, and `?` for steps the model only claimed. |

---

## Does it work? The evidence

![ForgeMySpec comparative results](experiments/forgemyspec_chart.png)

We ran 17 benchmark projects twice, once **with** a spec and once **without**. The runs used the earlier,
pre-Dafny version of ForgeMySpec.

| 17 projects | With spec | Without |
|---|:---:|:---:|
| **Total issues** | **8** | 16 |
| Functional bugs | 4 | 6 |
| Structural / conformance drift | **0** | 7 |
| Security vulnerabilities | **0** | 1 (`eval()` on user input) |
| Silent issues (no crash, still wrong) | 4 | 9 |
| Projects with zero issues | **10 / 17** | 6 / 17 |
| Average completeness | **4.85 / 5** | 4.17 / 5 |

**The gap grows with complexity:**

```
Simple projects   (P3, P10, P12, P15)        tie
Medium projects   (P1, P6, P8, P13, P17)     with spec +5–15% conformance
Complex projects  (P2, P4, P5, P11, P16)     with spec +15–40%; 0 vs 1+ vulnerability or critical drift
```

**Where it did not help.** Both bugs in project 2 happened *with* the spec. One was a routing loop that
short-circuited and the other was a read before commit. The spec described the HTTP interface but not those
pitfalls. Project 5 crashed on `Path | None` under Python 3.9. A spec does not replace technical knowledge.
In the first round the spec runs also needed more rework cycles (4 against 2): their bugs surfaced in
validation, while two of the issues without a spec shipped silently.

**What it costs.** We have not measured tokens yet: the benchmark measured issues and quality. The framework
adds context to every turn (skills, CLAUDE.md, the board) and adds steps (approvals, gate runs). Formal Dafny
bundles cost by far the most. Use them where an error is expensive. For ordinary work, use the spec-only path.

Full data: [`experiments/COMPARATIVE_REPORT.md`](experiments/COMPARATIVE_REPORT.md) ·
case study: [building a bare-metal OS](#case-study-a-bare-metal-os-from-five-words).

---

## Two levels of rigor

Every piece of work is a **bundle**: a folder with a `spec.yaml`. A bundle comes in one of two kinds:

```
                         ┌──────────────────────────────┐
                         │  /forgemyspec  →  spec.yaml  │
                         └──────────────┬───────────────┘
                 ordinary feature       │       critical logic (money, security,
                  (the default)         │        permissions) or you ask for proof
            ┌───────────────────────────┴───────────────────────────┐
            ▼                                                       ▼
   SPEC-ONLY                                               FORMAL (Dafny)
   approve  ── you type the code                           /forgemyspec-formalize
   Claude writes code + tests                                contract.dfy · tests.dfy · planted/
   gate: lint · coverage · spec lock ·                     lock  ── you type the code
         Python tests · verify_command                     /forgemyspec-implement
                                                             impl.dfy + Python shell
                                                           gate: + verify · audit · translate ·
                                                                   mutation · planted errors
```

| | Spec-only | Formal (Dafny) |
|---|---|---|
| **Use it for** | Features, UI, integration, scripts | Rules where a mistake is expensive |
| **What guarantees it** | Named Python tests and your `verify_command` | A Dafny proof against the contract you approved, attacked by mutants and planted errors |
| **You approve** | The spec (`approve` → `spec.lock`) | The contract, tests and planted errors (`lock` → `contract.lock`) |
| **Shows in the risk box as** | 🟡 tested with examples only | 🟢 proven by Dafny |
| **Cost** | Low | High: more tokens, more time, and Dafny installed |

---

## Install

You need Python 3.9+ with PyYAML. For formal bundles you also need Dafny 4.x (`brew install dafny`, or the
[Dafny releases](https://github.com/dafny-lang/dafny/releases)).

```bash
git clone https://github.com/ferrarimarlon/forgemyspec
pip install PyYAML
```

There are two ways to use it. **Pick one per project:**

| | 🔌 Plugin (light) | 🛡️ `init` (strict) |
|---|---|---|
| **How** | In Claude Code: `/plugin marketplace add /path/to/forgemyspec/plugin`, then `/plugin install forgemyspec@forgemyspec` | In **your** terminal: `PYTHONPATH=/path/to/forgemyspec/src python3 -m forgemyspec init /path/to/your-project` |
| Skills, agent, board | ✅ | ✅ |
| Guards on edits and shell commands | ✅ | ✅ |
| Harness copied into the repository (`.forgemyspec/harness`) | — | ✅ |
| Git **pre-commit** runs the gate | — | ✅ |
| **CI** workflow runs the gate (`.github/workflows/forgemyspec.yml`) | — | ✅ |
| CLAUDE.md block, `.gitignore`, config file | — | ✅ |

Neither path overwrites your files: `init` merges `settings.json`, keeps your old pre-commit hook as
`pre-commit.local`, and writes its CLAUDE.md block between markers.

### Maximum rigor recipe

1. Install with **`init`**, and commit the files it writes.
2. In `/forgemyspec`, ask for **`kind: dafny`** on every rule that can be proven. Leave `kind: boundary` only
   for I/O: files, network, parsing and CLI.
3. **Read the contract** before you type the code. The harness cannot check this step: Dafny proves the
   code meets the clauses, not that the clauses say what you meant.
4. Run the **full gate** before calling it done. `--fast` is only for iterating inside the session. The
   pre-commit hook and CI always run the full gate.
5. Never use `--no-verify` (the guard blocks it) or `suspend`.
6. Watch `forgemyspec risk`: the goal is **free ≈ 0%**.

---

## The flow, command by command

Inside Claude Code the skills are slash commands:

| Command | Claude writes | The harness checks | You do |
|---|---|---|---|
| `/forgemyspec` | `spec.yaml` (and `CLAUDE.md`, an acceptance checklist, scope evals) | `lint --formal`, coverage, `package` | Answer questions, read the obligations table |
| `/forgemyspec-formalize` | `contract.dfy`, `tests.dfy`, `planted/*.dfy` | Dafny lint (no vacuous or unsound contracts) | Read the contract, **type the code** → `lock` |
| `/forgemyspec-implement` | `impl.dfy`, Python shell, boundary tests | `gate` until every stage is PASS | Nothing; wait for PASS |
| `/forgemyspec-amend` | Only the minimal delta to the spec or contract | lint, diff | **Type the code** → `unlock`, then `lock`/`approve` again |
| `/forgemyspec-board` | A requirement for every request | `board verify` runs the checks | Ask `board R7` for details |

The `forgemyspec-default` agent preloads these skills and routes development work into the flow.

### Approval in the chat

```
Claude:  request-approval lock:examples/budget-core
Harness: approve with code  K7Q2XF   (contract.dfy, tests.dfy, planted/, formal: hashed)
You:     K7Q2XF
Claude:  lock examples/budget-core   →   approved by you in chat (K7Q2XF)
```

1. Claude runs `request-approval <action>:<target>`. The harness hashes what will be approved and prints a code
   derived from those hashes.
2. You **type the code**. The code counts only if **you** typed it, after the request, while the content still
   has the same hash, and only once. If the code shows up in Claude's own text, in a tool output or in a skill,
   it does not count. A proven kernel function, `DecideApproval`, makes this decision.
3. Running the command yourself in a terminal is an approval too.

The actions you can approve are `lock`, `approve`, `unlock`, `init` and `suspend`.

### The guards

| When | What happens |
|---|---|
| **Before a file edit** | An edit outside an approved bundle's `scope.paths` is **denied**, with the next step. Contracts, tests, planted errors, the `formal` section, locks, config and `generated/` are off limits to Claude. Free text in `allow_paths` (by default `*.md` and `docs/`) is allowed. |
| **Before a shell command** | `lock`, `approve`, `unlock`, `init`, `suspend`, `git commit --no-verify` and shell writes to protected paths are **denied** |
| **On session start and every prompt** | Each bundle's state and its next step enter Claude's context |
| **At the end of each turn** | A reply without the board goes back once to include it; the turn is written to the ledger |
| **On commit and in CI** (`init` only) | The full gate runs on bundles with staged changes and on every push |

The guards stop an **agent that drifts**. They do not stop an adversary: a shell command written to escape them
can get through, and pre-commit and CI are the safety net for that case.

---

## What you see

### The board: every request, verified or claimed

Every request you make becomes a requirement with your own words and checkable steps. Each reply ends with the
board, printed by the harness and never typed by Claude:

```
ForgeMySpec · 34 requirements
done      ███████████████████░ 33/34
doing     █░░░░░░░░░░░░░░░░░░░ 1
open      ░░░░░░░░░░░░░░░░░░░░ 0
blocked   ░░░░░░░░░░░░░░░░░░░░ 0

harness   █████████████████░░░ 83%  ✔ verified by checks (60/72 steps)
model     ██░░░░░░░░░░░░░░░░░░ 10%  ? claimed, no check (7)
activity  210 harness runs · 114 guard checks · 90 model writes · 875k tokens
memory    context 474k tokens
```

| Line | Meaning |
|---|---|
| `done / doing / open / blocked` | Requirements by status |
| `harness` | Share of steps **verified**: a `test:` or `cmd:` check ran and passed |
| `model` | Share of steps only **claimed** (`ok: true` with no check) |
| `activity` | Harness runs and guard checks against model writes, and the model's output tokens |
| `memory` | Size of the last context window |

`board R30` opens one requirement:

```
✅ R30 Top-notch board: verified, not self-declared
  progress ██████████ 100%
  effort H 70% M 30% · 27k tokens  (H = harness runs, M = model writes)
  contract:  ✔ verified  ↻ stale  ✗ failed  ? claimed  · to do
  ✔ tokens per requirement  [test: test_board.BoardTests.test_verified_only_by_a_passing_check]
  ✔ board tests  [test: test_board]
  you said: essa é a melhor caixa possível, profissional…
```

A step stays ✔ only while the code is unchanged. After a code change it turns ↻ (stale) until the check runs again.

### The risk box: how much room is left to hallucinate

```
ForgeMySpec · project risk
──────────────────────────────────────────
REQUIREMENTS: 7 of 7 met

▸ examples/budget-core
  strength: mutants 14/14 · planted errors 4/4
🟢 deposit adds exactly the amount        proven by Dafny
🟡 malformed line reported with line no.  tested with examples only

ROOM FOR THE LLM TO HALLUCINATE
proven        ███████████████░░░░░  74%    41 lines
examples only ████░░░░░░░░░░░░░░░░  19%    11 lines
free          █░░░░░░░░░░░░░░░░░░░   7%     4 lines

WHAT ONLY YOU GUARANTEE
· does the contract of examples/budget-core say what you meant?
```

| Color | Rule (proven in Dafny, applied to the gate's evidence) |
|---|---|
| 🟢 proven | A Dafny obligation that verified, and mutants and planted errors were killed |
| 🟡 fragile | Covered only by tests with examples (`kind: boundary`, spec-only bundles) |
| 🔴 leaking | Failing, never gated, or **changed since the last gate** |

The colors do not come from the model. The harness builds the box and spends no model tokens on it.

### The gate: what "PASS" means

| Stage | Spec-only | Formal | `--fast` skips it |
|---|:---:|:---:|:---:|
| spec lint, obligation coverage | ✅ | ✅ | |
| spec lock / contract lock (hashes unchanged) | ✅ | ✅ | |
| Dafny lint, toolchain | | ✅ | |
| `dafny verify` (proof) | | ✅ | |
| Dafny tests, `dafny audit` | | ✅ | |
| translation to Python (`generated/core-py`) | | ✅ | |
| Python boundary tests | ✅ | ✅ | runs only the obligations' tests |
| `verify_command` | ✅ | | ✅ skipped |
| **mutation**: mutants of the implementation must fail | | ✅ | ✅ skipped |
| **planted errors**: wrong implementations must be rejected | | ✅ | ✅ skipped |

---

## Command reference

Every command is `python3 -m forgemyspec <command>`, with the harness on `PYTHONPATH`:

```bash
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec …   # project installed with init
PYTHONPATH=<plugin>/harness     python3 -m forgemyspec …   # project using the plugin
PYTHONPATH=src                  python3 -m forgemyspec …   # inside this repository
```

**Claude runs** these:

| Command | Parameters | Does |
|---|---|---|
| `lint <spec.yaml>` | `--formal`: require the `formal` section, as the gate does | Checks structure, traceability, evidence quality and coverage. Exit 1 on errors |
| `package <spec.yaml>` | `--output-dir <dir>`: defaults to the spec's folder | Lints, then writes `CLAUDE.md`, `acceptance-checklist.md`, `.claude/commands/implement-from-spec.md` and `evals/scope_drift_cases.yaml` |
| `gate <bundle>` | `--all`: every approved bundle in the project · `--fast`: the in-session tier (see the table above) | Runs every stage and prints `RESULT: PASS` or `FAIL` |
| `risk` | `--json`: the panel's data as JSON instead of the box | Prints the risk box |
| `board [R<n>]` | `R7`: one requirement in full · `start R7`: mark the requirement being worked on · `verify [R7]`: run the `test:`/`cmd:` checks | Prints the requirements board |
| `request-approval <action>:<target> …` | items such as `lock:examples/budget-core`, `approve:my-feature`, `init:.` | Prints the code you type to approve |
| `lock <bundle> --check` / `approve <bundle> --check` | `--check`: run the checks, write nothing | Dry run of an approval |
| `kernel` | `--check`: compare with a fresh translation instead of writing · `--bundle <dir>`: default `forgemyspec-bundle/kernel` | Regenerates `src/forgemyspec/_kernel` from the Dafny kernel |
| `init <target> --check` | `--check`: compare only, exit 1 if something differs | Checks an installation |

**Only you run** these (or Claude, after you type the code):

| Command | Parameters | Does |
|---|---|---|
| `approve <bundle>` | | Approves a **spec-only** bundle: writes `spec.lock` |
| `lock <bundle>` | | Approves a **formal** bundle: writes `contract.lock` with the hashes of the contract, tests, planted errors and `formal` |
| `unlock <bundle>` | | Removes the lock so an amendment can happen |
| `init [target]` | `target`: default `.` · `--python <exe>`: interpreter the hooks use (default `python3`) | Installs ForgeMySpec into a repository |
| `suspend [target]` | `target`: default `.` | Turns the guards off and keeps bundles and locks. `init` turns them back on |

`hook <event>` is the internal entry point that Claude Code's hooks and pre-commit call.

---

## The files, field by field

### `spec.yaml`: the source of truth

Abridged from [`examples/budget-core/spec.yaml`](examples/budget-core/spec.yaml), plus a `scope` block:

```yaml
version: "0.1"
title: "Budget ledger core with a verified balance contract"
objective: "Replay a ledger of deposits and withdrawals, rejecting overdrafts…"
execution_mode: critical
context:
  system: "…"
  assumptions: ["Amounts are unbounded integers…"]
constraints: ["The shell refuses a negative opening balance…"]
success_criteria: ["`gate examples/budget-core` exits 0 with every stage PASS."]
required_evidence: ["Gate report for this bundle with every stage PASS, including the mutation kill rate."]
hypotheses:
  - {id: h1, description: "Deposits of a positive amount add exactly that amount…", confidence: 0.95}
actions:
  - {id: a1, type: implement, description: "…", supports: [h1]}
decision_rules: ["If a contract clause turns out to be unprovable as written, stop and amend… instead of weakening impl.dfy."]
metadata:
  source_prompt: "the user's request"
  scope_contract:
    must_include: ["deposit adds exactly the amount", "overdraft rejected"]
formal:
  module: BudgetCore
  obligations:
    - {id: deposit_exact, kind: dafny, statement: "…", hypotheses: [h1], must_include: ["deposit adds exactly the amount"]}
    - {id: malformed_line, kind: boundary, test: test_cli.CliTests.test_malformed_line_reports_line_number, …}
scope:                      # spec-only bundles
  paths: ["src/**", "tests/**"]
  tests: tests
  pythonpath: [src]
  verify_command: "npm test"
```

| Field | What it is | Rule the linter enforces |
|---|---|---|
| `version`, `title`, `objective` | What is being built and why | Required |
| `execution_mode` | Always `critical` | Required |
| `context.system`, `context.assumptions` | The environment and the explicit premises | At least 1 assumption |
| `constraints` | Hard limits, **including what stays out of scope** | At least 1 |
| `success_criteria` | What "done" means | At least 1 |
| `required_evidence` | Observable proof: test runs, command output | Never "the source code" |
| `hypotheses` | Affirmative, testable claims with `confidence` from 0 to 1 | No negations: exclusions go in `constraints` |
| `actions` | Steps of type `analyze`, `design`, `implement`, `validate` or `review` | `supports` must link only to the hypotheses the step advances |
| `decision_rules` | When to stop, escalate or choose | At least 1 |
| `metadata.source_prompt` | Your request, verbatim | Required |
| `metadata.scope_contract.must_include` | Short, exact phrases for every non-negotiable requirement | Each one becomes a line of the risk box |
| `formal.module` | Name of the abstract Dafny module | Formal bundles |
| `formal.obligations[]` | `id`, `kind`, `statement`, `hypotheses`, `must_include`, and `test` for boundary obligations | Every hypothesis and every `must_include` phrase must be covered |
| `kind: dafny` | Proven by Dafny | Critical, pure logic |
| `kind: boundary` | Tested in Python (`test: module.Class.method`) | I/O and the core's preconditions, because translated code does not check `requires` |
| `scope.paths` | Paths the bundle covers; the guards allow edits there after approval | Spec-only bundles |
| `scope.tests`, `scope.pythonpath` | The unittest folder and extra import paths | |
| `scope.verify_command` | Any command that must exit 0 (`npm test`, `cargo test`…) | |

Full schema: [`spec-schema.md`](plugins/forgemyspec/skills/forgemyspec/references/spec-schema.md).

### A formal bundle

```
<bundle>/
  spec.yaml          source of truth
  contract.dfy       abstract module: datatypes, spec functions, bodiless methods with clauses   (you approve)
  tests.dfy          {:test} methods with concrete examples, tagged per obligation             (you approve)
  planted/*.dfy      plausible wrong implementations; every one must be rejected              (you approve)
  contract.lock      hashes of the above + spec version                                       (only you write it)
  impl.dfy           module refining the contract
  shell/             hand-written Python I/O over the translated core
  tests_py/          boundary tests
  generated/core-py/ written by the gate; never edited by hand
```

### The board file

`forgemyspec-board.yaml` in your project:

```yaml
- id: R7
  status: doing                     # done | doing | open | blocked
  title: "Export the report as CSV"
  quote: "the user's own words"
  steps:
    - {do: "CSV has a header row", check: "test: tests.test_export.ExportTests.test_header"}
    - {do: "file opens in Excel", check: "cmd: python3 scripts/check_csv.py out.csv"}
    - {do: "the user likes the column order", ok: true}      # claimed: shown as ?
  evidence: "test output or command output"
  next: "what happens next"
```

| `check:` | Verified when |
|---|---|
| `test: module.Class.method` (or `test: module`) | The unittest passes |
| `cmd: <shell command>` | The command exits 0 |
| `ok: true` (no check) | Never: it counts as **claimed** |

### Configuration

`.forgemyspec/config.yaml` (written by `init`; only you edit it, and the guards protect it):

| Key | Default | Meaning |
|---|---|---|
| `enforcement` | `strict` | Guard mode |
| `allow_paths` | `**/*.md`, `docs/**`, `LICENSE*` | Free text Claude may edit without a bundle; the box lists it as unverified |
| `ignore_dirs` | `.git`, `node_modules`, `.venv`, `generated`, `build`, `dist`, … | Folders left out of the analysis |

`.forgemyspec-policy.yaml` (optional, or `FORGEMYSPEC_POLICY=/path`) tunes the gate:

| Key | Default | Meaning |
|---|---|---|
| `min_items` | 1 of each section | Minimum assumptions, constraints, criteria, hypotheses, evidence, actions, rules |
| `allowed_action_types` | `analyze, design, implement, validate, review` | Valid `actions[].type` |
| `require_action_support_links` | `true` | Every action must link to hypotheses |
| `required_metadata_fields` | `[source_prompt]` | Required `metadata` keys |
| `lint_min_passing_score` | `70` | Minimum lint score |
| `mutation_min_kill_rate` | `0.9` | Share of mutants that must fail |
| `max_mutants` | `40` | Mutants generated per gate |
| `min_planted_errors` | `3` | Minimum planted wrong implementations |
| `dafny_min_version` | `"4.0"` | Oldest accepted Dafny |
| `dafny_timeout_seconds` | `300` | Timeout per Dafny run |

---

## Example: `examples/budget-core`

A ledger of deposits and withdrawals. The rules are proven in Dafny and reach users through a small Python CLI.

```bash
PYTHONPATH=src python3 -m forgemyspec lock examples/budget-core     # you approve the contract
PYTHONPATH=src python3 -m forgemyspec gate examples/budget-core     # RESULT: PASS
```

| File | Role |
| --- | --- |
| [`spec.yaml`](examples/budget-core/spec.yaml) | Hypotheses, scope phrases and 8 obligations (6 Dafny, 2 boundary) |
| [`contract.dfy`](examples/budget-core/contract.dfy) | `abstract module BudgetCore`: exact outcomes for deposit and withdraw, overdraft rejection, non-negative balances, replay |
| [`tests.dfy`](examples/budget-core/tests.dfy) | Concrete examples per obligation, including the edge case `withdraw(10, 10)` |
| [`planted/`](examples/budget-core/planted) | 4 planted errors: exact-balance withdrawal, zero deposit accepted, no balance check, rejection not counted |
| [`impl.dfy`](examples/budget-core/impl.dfy) | `module BudgetImpl refines BudgetCore`, with replay proven by loop invariants |
| [`shell/budget_cli.py`](examples/budget-core/shell/budget_cli.py) | Parsing, printing and the `start >= 0` precondition |
| [`tests_py/test_cli.py`](examples/budget-core/tests_py/test_cli.py) | Boundary tests against the translated core |

```
$ printf 'deposit 10\nwithdraw 4\nwithdraw 7\ndeposit -1\ndeposit 2\n' > ledger.txt
$ PYTHONPATH=examples/budget-core/generated/core-py:examples/budget-core \
    python3 -m shell.budget_cli ledger.txt
balance=8 rejected=2
```

---

## Trusted base

| Layer | How it is guaranteed |
|---|---|
| The five trust decisions: each obligation's color, each requirement's status, the guards' edit decision, coverage, and whether an approval counts | **Proven in Dafny** in [`forgemyspec-bundle/kernel`](forgemyspec-bundle/kernel), with 29 proof obligations, 15 Dafny tests and 9 planted errors. Python uses only the translation, and CI checks that it matches a fresh one |
| The logic of your formal bundles | **Proven in Dafny** against the contract you approved, and attacked with mutants and planted errors |
| The Python glue: file reading, path categories, shell parsing, rendering | **Tested** (`tests/`, more than 70 tests, including the guards' decision tables and fault injection) |
| Your `kind: boundary` code and spec-only bundles | **Tested with examples** |
| What you still trust | Dafny and Z3, Python, git, Claude Code's session transcript, and **your approval of each contract** |

The residual risk no harness removes: **the contract may not say what you meant.** That is why the contract is
short, comes with concrete examples and planted errors, only you lock it, and the box reminds you of it.

---

## Why: the context stack dilutes your request

In Claude Code, each turn draws on far more than your latest message:

```
1. Claude Code / platform instructions
2. Project memory: CLAUDE.md, settings, repo rules
3. Skills
4. MCP servers: live data and tools
5. Your current request              ← shrinks relative to everything else
6. Conversation history
7. Tool outputs: diffs, logs, file reads
```

The requirement you typed competes with everything else in the window. Missing details get filled in by
pattern matching, "helpful" extras slip in, and the model reports the work as done in broad terms.
ForgeMySpec writes the request down as files that Claude re-reads, and it moves "done" out of the conversation:
"done" becomes a proof, a test or a lock, and none of those depend on what the model remembers.

---

## Case study: a bare-metal OS from five words

*(earlier, pre-Dafny version)* The [`experiments/mini-os/`](experiments/mini-os) directory is a complete run.
From the seed `build a simple operating system`, ForgeMySpec compiled a full spec, and `/implement-from-spec`
built a bootable x86 disk image.

![MiniOS v0.1 running in QEMU: boot summary, memory map, and GDT](docs/minios-qemu.png)

**The input.** The seed is the five words. `metadata.source_prompt` in
[`spec.yaml`](experiments/mini-os/spec.yaml) adds the path, the architecture (x86 bare metal), "no external
libraries", the deliverables (bootloader + kernel, VGA text) and the run target (QEMU). Together they are the
complete, replayable input.

**The objective the spec fixed:** a 512-byte BIOS bootloader and a freestanding C kernel, writing VGA text and
booting in QEMU from a raw disk image, with no libraries and no runtime.

| Hard constraints | Hypotheses (confidence) |
|---|---|
| Bootloader exactly 512 bytes, ending in `0xAA55` | h1: a NASM bootloader can switch to protected mode and jump to C at `0x1000` (0.95) |
| Freestanding C: no libc, no crt0 | h2: the kernel can write to the VGA buffer at `0xB8000` (0.97) |
| Toolchain `nasm` + `gcc -m32` + `ld` only | h3: a Makefile with only those tools produces a bootable image (0.92) |
| `make run` boots it in QEMU | |

**The actions:** a1 design the layout → a2 `boot.asm` → a3 `kernel.c` → a4 `linker.ld` → a5 `Makefile` →
a6 validate. Each action links to the hypotheses it supports, so the spec can be audited as a graph.

**The scope fence.** The spec required the bootloader, the protected-mode switch, the C kernel, VGA, the
Makefile and the QEMU target. It excluded libc, filesystems, keyboard and interrupts, multitasking, and anything
outside the folder. Eleven machine-checkable seeds in `evals/scope_drift_cases.yaml` enforce this: 6 patterns
that must never appear (`stdio.h`, IDT setup, scheduler keywords) and 5 values that must be present (`0xAA55`,
`0xB8000`, `-ffreestanding`).

**The evidence:**

```
$ make
  [OK] boot.bin     512 bytes
  [OK] kernel.bin   2445 bytes
  [OK] os.img       65536 bytes
  [OK] magic        55aa

$ qemu debug port output:
MiniOS v0.1 — kernel_main reached
[BOOT] Bootloader: 0x7C00  Kernel: 0x1000  Stack: 0x90000
[MEM]  VGA: 0xB8000  Conv: 0x00000-0x9FFFF
[GDT]  Code: 0x08  Data: 0x10
Kernel halted. All systems nominal.
```

### Errors stopped before the first boot

![Errors surfaced per development phase: Spec-Driven vs No Spec](docs/error-phase-comparison.svg)

| Failure | Symptom without the spec | What the spec said first |
|---|---|---|
| Linker emits ELF instead of a raw binary | Black screen, which looks the same as a wrong load address or a missing signature | Always pass `--oformat binary` |
| Bootloader grows past 512 bytes | The BIOS refuses to boot, with no error | Trim strings and data first; **keep the signature** |
| VGA bytes swapped | Glyphs that look alive and are unreadable | Character byte first, color byte second, written into the contract |
| Scope creep: keyboard, scheduler, interrupts | Additions that feel helpful pile up quietly | An explicit exclusion list, checked by the scope evals |

**Discoveries kept as memory.** Two failures showed up at runtime first. The compiler placed a helper function
at the kernel's entry address, so the bootloader jumped into it. And `-m32` fails on Apple Silicon, with an error
that looks like a missing toolchain. Both fixes went into a memory file the agent reads at the start of every
session, so every later run writes the correct code from the start.

---

## Repository layout

```
src/forgemyspec/           deterministic harness (Python 3.9+, PyYAML only)
├── __main__.py            the CLI (every command above)
├── kernel.py + _kernel/   bridge to the trust kernel translated from Dafny (never edited by hand)
├── hooks.py               guards, Stop, state injection, pre-commit
├── board.py               requirements board
├── risk.py                risk box
├── gate.py                gate stages, per-obligation evidence, planted errors
├── linting.py             spec lint and coverage (LINT-*, LINT-FORMAL-*)
├── dafny_lint.py          Dafny scanner and contract rules (LINT-DFY-*)
├── approvals.py           approval codes in the chat
├── contract_lock.py       contract and spec locks
├── install.py             init and suspend
└── messages.py            every user-facing text
plugins/forgemyspec/       canonical skills and the default agent (symlinked into .claude/)
plugin/                    the installable plugin, built by scripts/build_plugin.py
forgemyspec-bundle/        the specs ForgeMySpec was built from, including the proven kernel and its own board
examples/budget-core/      end-to-end formal bundle
experiments/               benchmark data behind the numbers above, and the mini-os case study
tests/                     harness tests
```

Dafny lessons learned while building the harness are in
[`dafny-patterns.md`](plugins/forgemyspec/skills/forgemyspec/references/dafny-patterns.md).

## What's next

- **Measure tokens**: run the same tasks with and without ForgeMySpec and compare the cost per correct task.
- A fixed panel next to the chat, updated only by the harness, at zero tokens.
- Conflict mediation for specs with contradictory requirements.
