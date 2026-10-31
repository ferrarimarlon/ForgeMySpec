# ForgeMySpec

[![Tests](https://github.com/ferrarimarlon/forgemyspec/actions/workflows/tests.yml/badge.svg)](https://github.com/ferrarimarlon/forgemyspec/actions/workflows/tests.yml)

**Turn a request into a contract that a machine checks — before an AI writes the code that has to meet it.**

ForgeMySpec is a harness for **Claude Code**. Claude writes the spec, a Dafny contract and the implementation
inside your session. A deterministic harness (no LLM, no network) proves, tests, audits, attacks with mutants
and planted errors, and locks the result, and only then translates the verified core to Python.

The goal is maximum harness and minimum hallucination. Every requirement ends up as either a **proof
obligation** checked by the Dafny verifier or a **named test**. The contract you approve cannot be quietly
weakened afterwards, and the guards stop Claude from skipping the flow.

## Why Use This?

![ForgeMySpec comparative results](experiments/forgemyspec_chart.png)

ForgeMySpec matters most when the task stops being trivial. Once a requirement has interacting rules, validation paths, derived fields, security constraints, or multiple edge cases, “just write the code” starts to look correct long before it is actually safe or complete. ForgeMySpec turns that ambiguity into an executable contract first, so the agent implements against a stable target instead of improvising under context pressure.

Across 17 benchmark projects (run with the earlier, pre-Dafny version of ForgeMySpec), both approaches usually produced something that looked functional. The difference showed up in the parts that are expensive to discover later: silent bugs, structural drift, and security mistakes that do not necessarily break the happy path. ForgeMySpec consistently held quality higher, and the gap widened as the scenarios became more complex.

| | With spec | Without |
|---|:---:|:---:|
| Average completeness | 4.85 / 5 | 4.17 / 5 |
| Security vulnerabilities | 0 | 1 |
| Structural deviations | 0 | 7 |
| Silent quality issues | 4 | 9 |
| Projects with zero issues | 10 / 17 | 6 / 17 |

**The more domain pressure you add, the more ForgeMySpec pulls away.** In simple, closed tasks, direct implementation can be enough. In medium and complex projects, the spec preserves intent while the agent navigates multiple constraints at once. Hidden drift usually starts there, and ForgeMySpec keeps the implementation anchored to the requirement.

That advantage matters in the places teams actually pay for mistakes: approval flows, invariants, conditional rules, security boundaries, and business logic that cannot be reconstructed reliably from the final code alone. ForgeMySpec keeps those constraints explicit from the start and gives the agent a tighter target to execute against.

For tiny one-off scripts, the extra structure may not matter. For work with multiple interacting constraints and real failure modes, ForgeMySpec gives the agent a measurable advantage.

Full data: [`experiments/COMPARATIVE_REPORT.md`](experiments/COMPARATIVE_REPORT.md)

---

## How it works

```
/forgemyspec            Claude writes spec.yaml                          harness: lint, coverage
        │
/forgemyspec-formalize  Claude writes contract.dfy, tests.dfy, planted/
        │               ── YOU approve by running `lock` in your terminal ── harness: lock (SHA-256)
        │
/forgemyspec-implement  Claude writes impl.dfy and the Python shell      harness: gate
                                                                          → generated/core-py (verified Python)
```

| Step | Who | What is checked, deterministically |
| --- | --- | --- |
| Spec | Claude | Structure, traceability (actions → hypotheses), evidence quality and **coverage**: every `must_include` phrase and every hypothesis maps to a Dafny obligation or a named Python test |
| Contract | Claude, approved by **you** | An abstract Dafny module with clauses tagged per obligation, tests with concrete examples, and planted errors. Vacuous or unsound constructs are rejected. The lock records hashes of the contract, tests, planted errors and obligation map |
| Implementation | Claude | A module that *refines* the contract. It must verify, pass the tests and `dafny audit`, **kill the mutants** and **reject every planted error** |

### The guards (strict mode)

`forgemyspec init` installs Claude Code hooks that run the harness on every action:

| When | What happens |
|---|---|
| Before a file edit | An edit outside an approved spec is **denied**, with the next step. Contract, tests, planted errors, the formal section, locks, configuration and `generated/` are off limits to Claude |
| Before a shell command | `lock`, `approve`, `unlock`, `init`, `git commit --no-verify` and shell writes to denied paths are **denied** |
| At the end of each turn | An approved bundle without a passing gate for its current content **blocks "done"**; after 3 attempts the turn is released with "WORK NOT VERIFIED" |
| On every prompt | Each bundle's state and next step enter Claude's context |
| On commit and in CI | The same gate runs in the pre-commit hook and in the `ForgeMySpec gate` workflow |

### The risk box

At the end of every turn a box appears. The harness builds it, and it spends no model tokens:

```
ForgeMySpec · project risk
──────────────────────────────────────────

REQUIREMENTS: 7 of 7 met

▸ examples/budget-core
  strength: mutants 14/14 · planted errors 4/4
🟢 deposit adds exactly the amount
   proven by Dafny
🟡 malformed line reported with line number
   tested with examples only

ROOM FOR THE LLM TO HALLUCINATE
proven        ███████████████░░░░░  74%    41 lines
examples only ████░░░░░░░░░░░░░░░░  19%    11 lines
free          █░░░░░░░░░░░░░░░░░░░   7%     4 lines

WHERE IT LEAKS
· …

WHAT ONLY YOU GUARANTEE
· does the contract of examples/budget-core say what you meant?
    approved by you on …
```

No color comes from the LLM: **proven**, **fragile** and **leaking** come from fixed rules, proven in Dafny,
applied to the gate's evidence.

---

## Trusted base

What you need to know to decide how much to trust it:

| Layer | How it is guaranteed |
|---|---|
| The four trust decisions: each obligation's color, each requirement's status, the guards' edit decision and coverage | **Proven in Dafny** in the kernel [`forgemyspec-bundle/kernel`](forgemyspec-bundle/kernel): 25 proof obligations, 12 Dafny tests and 6 planted errors. Python uses only the translation, and CI checks that it matches a fresh translation |
| The logic of each of your projects (whatever is `kind: dafny`) | **Proven in Dafny** against the contract you approved, and attacked with mutants and planted errors |
| The Python glue: reading files, path categories, parsing shell commands, building the box | **Tested**, not proven (`tests/`, more than 60 tests, including the guards' decision tables and fault injection) |
| Your code that is `kind: boundary` or in a spec-only bundle | **Tested with examples**: it shows as "examples only" in the box |
| What you still trust | the Dafny verifier and Z3, Python, git, and **your approval of each contract** |

The residual risk no harness removes: **the contract may not say what you meant.** Dafny proves the code meets
the clauses, not that the clauses are your intent. That is why the contract is short, comes with concrete
examples and planted errors, only you lock it, and the box reminds you on every prompt.

The guards cover an **agent that drifts**, not an adversary: a shell command built to escape them can get
through, and pre-commit and CI are the safety net for that.

---

## Quick start

Requirements: Python 3.9+, PyYAML and Dafny 4.x (`brew install dafny`, or the
[Dafny releases](https://github.com/dafny-lang/dafny/releases)).

```bash
git clone https://github.com/ferrarimarlon/forgemyspec && cd forgemyspec
pip install PyYAML
PYTHONPATH=src python3 -m forgemyspec lock examples/budget-core     # you approve the example's contract
PYTHONPATH=src python3 -m forgemyspec gate examples/budget-core     # RESULT: PASS
```

To use it in your own project, install it there by running **in your terminal**:

```bash
PYTHONPATH=/path/to/forgemyspec/src python3 -m forgemyspec init /path/to/your-project
```

Then open the project in Claude Code. The skills become commands:

| Command | Does |
| --- | --- |
| `/forgemyspec` | Grounds the request (code, MCP sources) and writes `spec.yaml` with its `formal` section; lint and package |
| `/forgemyspec-formalize` | Writes `contract.dfy`, `tests.dfy` and `planted/`, and asks for your approval |
| `/forgemyspec-implement` | Writes `impl.dfy`, the Python shell and boundary tests, and runs the gate until it passes |
| `/forgemyspec-amend` | Changes the minimal delta when the spec or contract is wrong, with new approval |

Harness commands (deterministic, from the repository root):

```bash
python3 -m forgemyspec lint <spec.yaml> [--formal]
python3 -m forgemyspec package <spec.yaml>
python3 -m forgemyspec gate <bundle> | --all
python3 -m forgemyspec risk
python3 -m forgemyspec lock <bundle> [--check]       # user only (except --check)
python3 -m forgemyspec approve <bundle> [--check]    # user only: spec-only bundles
python3 -m forgemyspec unlock <bundle>               # user only
python3 -m forgemyspec init [target] [--check]       # user only
python3 -m forgemyspec kernel [--check]              # regenerate or check src/forgemyspec/_kernel
```

---

## Example: `examples/budget-core`

A ledger of deposits and withdrawals. The rules are proven in Dafny and reach users through a small Python CLI.

| File | Role |
| --- | --- |
| [`spec.yaml`](examples/budget-core/spec.yaml) | Hypotheses, scope phrases and 8 obligations (6 Dafny, 2 boundary) |
| [`contract.dfy`](examples/budget-core/contract.dfy) | `abstract module BudgetCore`: exact outcomes for deposit and withdraw, overdraft rejection, non-negative balances and replay defined by a spec function |
| [`tests.dfy`](examples/budget-core/tests.dfy) | Concrete examples per obligation, including the edge `withdraw(10, 10)` |
| [`planted/`](examples/budget-core/planted) | 4 planted errors: exact-balance withdrawal, zero deposit accepted, withdrawal without a balance check, rejection not counted |
| [`impl.dfy`](examples/budget-core/impl.dfy) | `module BudgetImpl refines BudgetCore`, with replay proven by loop invariants |
| [`shell/budget_cli.py`](examples/budget-core/shell/budget_cli.py) | Parsing, printing and the `start >= 0` precondition (translated code does not check `requires`) |
| [`tests_py/test_cli.py`](examples/budget-core/tests_py/test_cli.py) | Boundary tests against the translated core |

```
$ printf 'deposit 10\nwithdraw 4\nwithdraw 7\ndeposit -1\ndeposit 2\n' > ledger.txt
$ PYTHONPATH=examples/budget-core/generated/core-py:examples/budget-core \
    python3 -m shell.budget_cli ledger.txt
balance=8 rejected=2
```

(`generated/` is written by the gate; run the gate once first.)

---

## Spec structure

`spec.yaml` is the source of truth; every other file is a view of it or a check against it. The full schema
is in [`spec-schema.md`](plugins/forgemyspec/skills/forgemyspec/references/spec-schema.md).

| Area | Fields | Role |
|---|---|---|
| Identity | `version`, `title`, `objective` | What is being built and why |
| Execution | `execution_mode` | Always `critical` |
| Context | `context.system`, `context.assumptions` | Environment framing and explicit premises |
| Boundaries | `constraints` | Hard limits, including what stays out of scope |
| Outcomes | `success_criteria`, `required_evidence` | What "done" means and what observable proof is required |
| Reasoning | `hypotheses` | Affirmative, testable beliefs with `confidence` (0–1) |
| Work plan | `actions` | Steps whose `supports` link to the hypotheses they advance |
| Governance | `decision_rules` | When to stop, escalate or choose |
| Provenance | `metadata` | `source_prompt`, `generator`, `scope_contract.must_include` |
| Formal map | `formal` | Contract module name and the obligations (Dafny or boundary) that cover every requirement |
| Path coverage | `scope` | Paths, tests and verify command of spec-only bundles |

---

## Compiler policy

An optional `./.forgemyspec-policy.yaml` (or `FORGEMYSPEC_POLICY=/path`) tunes the gate:

```yaml
min_items: {assumptions: 1, constraints: 1, success_criteria: 1, hypotheses: 1,
            required_evidence: 1, actions: 1, decision_rules: 1}
allowed_action_types: [analyze, design, implement, validate, review]
require_action_support_links: true
required_metadata_fields: [source_prompt]
lint_min_passing_score: 70
mutation_min_kill_rate: 0.9
max_mutants: 40
min_planted_errors: 3
dafny_min_version: "4.0"
dafny_timeout_seconds: 300
```

The guards' configuration lives in `.forgemyspec/config.yaml` (mode, `allow_paths`, ignored folders). Only you edit it.

---

## Repository layout

```
src/forgemyspec/           deterministic harness (Python 3.9+, PyYAML only)
├── __main__.py            lint · package · lock · approve · unlock · gate · risk · kernel · init · hook
├── kernel.py + _kernel/   bridge to the trust kernel translated from Dafny (never edited by hand)
├── hooks.py               guards, Stop, state injection, pre-commit
├── risk.py                risk box
├── gate.py                gate stages, per-obligation evidence, planted errors
├── linting.py             spec lint and coverage (LINT-*, LINT-FORMAL-*)
├── dafny_lint.py          Dafny scanner and contract rules (LINT-DFY-*)
├── contract_lock.py       contract (v2) and spec locks
├── install.py             forgemyspec init
├── messages.py            every user-facing text
├── project.py · mutation.py · dafny_runner.py · claude_skill.py · spec_io.py · nlp_policy.py · bundle.py
plugins/forgemyspec/       skills and the default agent (symlinked into .claude/)
forgemyspec-bundle/        the specs ForgeMySpec was built from, including the proven kernel
examples/budget-core/      end-to-end formal bundle
experiments/               benchmark data behind the numbers above, and the mini-os case study
tests/                     harness tests: guards, init, gate, kernel, messages, fault injection
```

Dafny lessons learned while building the harness are in
[`dafny-patterns.md`](plugins/forgemyspec/skills/forgemyspec/references/dafny-patterns.md).

## The Problem

In **Claude Code**, each turn draws on more than the latest user message. Each turn is assembled from a **stack of context sources**—the same architecture that makes the agent capable also dilutes any single requirement over time.

Roughly, that stack looks like this:

```
1. Claude Code / platform instructions
2. Project memory — CLAUDE.md, settings, and repo-local rules
3. Skills — .claude/skills/ (instructions loaded when relevant)
4. MCP servers — live data and tools (issues, docs, APIs) merged into the session
5. Current user request              ← shrinks relative to everything else
6. Conversation history
7. Tool outputs — diffs, logs, command output, file reads
```

The **effective context window** is shared across all of that. So the explicit task you typed is only one slice of what the model must attend to. The stack is powerful — and it is exactly where **drift** begins: the requirement competes with skills output, MCP payloads, and accumulated tool traces.

From there, missing details get silently filled by pattern-matching. “Helpful” additions slip in because no hard execution contract exists. Completion gets reported in broad language even when acceptance criteria remain fuzzy.

ForgeMySpec answers this by materializing the request as files the agent re-reads as the context stack grows,
and by moving the definition of "done" out of the conversation: it becomes a proof, a test or a lock, none of
which depend on what the model remembers.

---

## Case study: building a bare-metal OS (earlier, pre-Dafny version)

The `experiments/mini-os/` directory is a complete end-to-end demonstration. ForgeMySpec compiled a full spec from a **short seed phrase**, and `/implement-from-spec` built a bootable x86 disk image.

![MiniOS v0.1 running in QEMU — boot summary, memory map, and GDT](docs/minios-qemu.png)

### The original prompt

The checked-in `experiments/mini-os/spec.yaml` stores a fuller `metadata.source_prompt` (what the compiler session actually recorded): path, architecture, and tooling constraints layered on top of that seed:

```yaml
source_prompt: >
  build a simple operating system
```

**What this case study documents**

| Layer | Content |
| --- | --- |
| **Seed** | Five-word phrase: `build a simple operating system`. |
| **Full prompt record** | `metadata.source_prompt` in `spec.yaml` adds the repository path, architecture (x86 bare-metal), stack constraints (minimal resources, no external libraries), deliverables (bootloader + kernel, VGA text), and run target (QEMU). |

Seed plus metadata together are the complete, replayable input stored on disk.

### What the spec compiled

Running `/forgemyspec` with that prompt text produced the full bundle in one pass:

**Objective** — 512-byte BIOS bootloader + freestanding C kernel → VGA text output → boots in QEMU from a raw disk image. No external libraries. No runtime.

**Hard constraints from `spec.yaml`:**
- Bootloader must be exactly 512 bytes, ending with `0xAA55` BIOS signature
- Kernel is freestanding C only — no libc, no crt0, no runtime
- Zero external libraries; toolchain is `nasm` + `gcc -m32` + `ld`
- All files inside `experiments/mini-os/`
- `make run` is the single command to boot in QEMU

**Hypotheses the spec reasoned over:**

| ID | Claim | Confidence |
|---|---|---|
| h1 | A 512-byte NASM bootloader can load, switch to protected mode, and hand off to a C kernel at `0x1000` | 0.95 |
| h2 | A freestanding C kernel can write directly to VGA framebuffer `0xB8000`, producing readable coloured output | 0.97 |
| h3 | A Makefile using only nasm + gcc -m32 + ld can produce a bootable raw image runnable in `qemu-system-x86_64` | 0.92 |

**Actions the spec decomposed the work into:**

| ID | Type | Description |
|---|---|---|
| a1 | design | Create directory layout: `boot/`, `kernel/`, `linker.ld`, `Makefile` |
| a2 | implement | Write `boot/boot.asm` — 16-bit startup, INT 13h disk read, A20, GDT, protected-mode switch, jump to `0x1000` |
| a3 | implement | Write `kernel/kernel.c` — VGA helpers and `kernel_main` banner |
| a4 | implement | Write `linker.ld` — sections at `0x1000`, flat binary output |
| a5 | implement | Write `Makefile` — `all`, `run`, `clean` targets; produce `build/os.img` |
| a6 | validate | Run `make`, check `boot.bin` size, boot in QEMU, verify VGA output |

Each action declares `supports` links to the hypotheses it validates — the spec is auditable as a graph.

**Scope contract — what the spec explicitly fenced out** (at the time, the schema still had `must_not_include`; exclusions now live in `constraints`):

```yaml
must_include:
  - 512-byte bootloader (NASM)
  - protected-mode switch
  - freestanding C kernel
  - VGA text output
  - Makefile
  - QEMU run target

must_not_include:
  - libc or any runtime library
  - filesystem driver
  - keyboard or interrupt handling
  - multitasking or scheduling
  - anything outside the project directory
```

### Scope drift evaluation

`evals/scope_drift_cases.yaml` holds 11 machine-checkable seeds derived from the spec:

- **6 negative checks** — patterns that must never appear: `#include <stdio.h>`, `-lpthread`, IDT setup, scheduler keywords
- **5 positive checks** — files that must exist and contain specific values: `0xAA55`, `0xB8000`, `-ffreestanding`

### Implementation and evidence

Running `/implement-from-spec` executed the six actions in order. The acceptance checklist was filled with **concrete evidence** (command output, sizes, hex dumps):

```
$ make
  [OK] boot.bin     512 bytes
  [OK] kernel.bin   2445 bytes
  [OK] os.img       65536 bytes
  [OK] magic        55aa

$ xxd -s 510 -l 2 build/os.img
000001fe: 55aa

$ qemu debug port output:
MiniOS v0.1 — kernel_main reached
[BOOT] Bootloader: 0x7C00  Kernel: 0x1000  Stack: 0x90000
[MEM]  VGA: 0xB8000  Conv: 0x00000-0x9FFFF
[GDT]  Code: 0x08  Data: 0x10
Kernel halted. All systems nominal.
```

All acceptance criteria passed: `make` exits 0, `boot.bin` is exactly 512 bytes, bytes 510–511 are `55 AA`, the kernel banner appears in QEMU with coloured VGA sections, and `make clean` removes all artefacts.

### What the spec prevented

The key shift is *when* the error surfaced: **during spec authoring**, before QEMU or the first boot attempt.

![Errors surfaced per development phase: Spec-Driven vs No Spec](docs/error-phase-comparison.svg)

A spec front-loads known failure modes before the first file exists. The agent reads them during implementation and writes code that already satisfies those constraints, so several failure classes **never reach** a QEMU run. Naming risky cases up front shortens the write → run → diagnose cycle.

#### Errors caught while writing

**Wrong linker output format.** The linker defaults to ELF format even when you need a raw binary. QEMU loads the image, the boot check passes, and execution lands in ELF header bytes; the kernel entry never runs. The screen goes black — identical in appearance to a wrong load address or a missing boot signature. Three different root causes, one symptom; foreknowledge matters. The spec had the fix written down before the Makefile existed: always pass `--oformat binary`. The agent applied it during authoring, avoiding the all-black screen entirely.

**Bootloader overflow.** The bootloader must fit in exactly 512 bytes, and the last two bytes are a fixed boot signature the BIOS requires to recognize the disk as bootable. If the binary grows too large and you trim the wrong bytes, the machine refuses to boot with no error output. The spec made the priority explicit before the assembler file was written: trim strings or data first; **preserve the boot signature**. The agent followed that ordering under the same constraints everyone else faces.

**Garbled screen output.** Each character cell on the screen is encoded as two bytes: color first, character second. Swapping the order fills the screen with glyphs that look alive but stay unreadable. The correct encoding was in the spec before the display code was written; the first VGA write matched that contract.

#### Runtime discoveries folded into persistent memory

A few failures surfaced first in QEMU or on the host. Each was logged into a persistent memory file the agent reads at the start of every session, so the next run starts with that knowledge already in place.

**Wrong function at the kernel entry point.** The bootloader jumps to a fixed memory address expecting to land on the kernel's main function. But the C compiler places functions in whatever order it chooses — and helper functions like screen clear or string print often end up before the main function in the final binary. The bootloader lands in the middle of a helper, the kernel crashes silently, and nothing appears on screen. Once discovered, the fix — forcing the entry point to always be first — was logged permanently. Every subsequent run inherits it and writes the correct code from the start.

**Compiler incompatibility on Apple Silicon.** On Apple Silicon Macs, the standard 32-bit compile flag fails with messages that resemble a missing toolchain install. The underlying issue is architecture mismatch; documenting the correct cross-compiler and flags carried that knowledge forward to every future run on that platform.

#### Scope creep — silent expansion until late review

An agent asked to "build a simple OS" has a natural instinct to keep adding things: keyboard input, a basic scheduler, interrupt handling. Each addition feels helpful. None of them announce themselves as out of scope — they just accumulate quietly.

The spec's explicit exclusion list made the boundary visible **before** implementation began. Late review no longer had to discover an OS that overshot the original ask by surprise.

---

## What's next

- A fixed panel next to the chat, updated only by the harness: clickable requirements, usage and adherence counters, zero tokens.
- Conflict mediation for specs with contradictory requirements.
