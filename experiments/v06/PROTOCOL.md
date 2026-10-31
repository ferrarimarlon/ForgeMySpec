# ForgeMySpec v0.6 experiment: protocol (pre-registered)

Committed before any measured run. Any later deviation is listed in the report under "Deviations".

## Question

With the current framework (v0.6: spec-only by default, Dafny only where the framework judges it critical,
approvals, guards, gate, board), compared with plain Claude Code on the same prompt:

1. Is the delivered code more correct and more secure, as judged blind?
2. How many tokens and how much money does each arm spend?
3. How much of the work is done by the harness and how much by the model?
4. Which level of rigor does the framework choose for each task (spec-only or formal), and does that choice track
   how critical the task is?

## Tasks

The 17 projects of the earlier benchmark plus the mini-OS case study: 18 prompts in [`tasks/`](tasks), frozen in
this commit. Both arms receive the **same prompt, byte for byte**.

- P01–P05, P16, P17 and P18 reproduce the original prompts. P18 only drops the original output path
  (it builds in the current directory).
- P06–P15: the original prompts survived only as one-line summaries. They were rewritten from those summaries and
  the project descriptions in `experiments/COMPARATIVE_REPORT.md`, at the level of detail of P01–P05, without
  any detail taken from the earlier framework specs.

## Arms

| | without | with |
|---|---|---|
| Directory | empty git repository | empty git repository + `forgemyspec init` (guards, skills, agent, board, pre-commit, CI) |
| Prompt | task prompt | the same task prompt; the framework is never mentioned |
| Everything else | identical | identical |

The framework decides by itself how to proceed. Whether it followed its flow and which rigor it chose are
outcomes, not inputs.

## Isolation

- Each build is a separate headless process: `claude -p` with `--model claude-sonnet-5-5`, pinned for every
  build, run by a frozen copy of Claude Code 2.1.296. The resolved model id is recorded. It is not a subagent of the session that runs the experiment, so no
  context, memory or instructions of that session reach the builder.
- The directory is under `/private/tmp/fms-v06/runs/`, outside the home directory, so no CLAUDE.md of the
  experimenter applies. Flags: `--setting-sources project,local` (no user settings, plugins or permissions),
  `--strict-mcp-config` with no servers (no MCP), and `--permission-mode bypassPermissions`. The ForgeMySpec
  guards are hooks and still deny in the with arm. Every `CLAUDE*` environment variable of the parent session
  is removed. A new path gives an empty auto-memory.
- The runs of a task never overlap: P02 uses port 8080, and P05 and P16 write to `~`. Their home folders are
  wiped before every run and archived after it. Different tasks run in parallel (3 workers).
- The order of the arms is shuffled within each repetition (seed `20261031`).

## The user's side, automated identically for both arms

- **Approver (with arm only).** When a turn ends with a new approval request in `.forgemyspec/state/approvals.json`,
  the driver runs the requested `approve`, `lock` or `unlock` in a pseudo-terminal, which is the "user runs it in
  their own terminal" path. It then resumes the session with the command output. It approves the first proposal
  unchanged and never reviews it, and it refuses `init` and `suspend`. Chat-typed codes cannot be used: under
  `claude -p` the transcript does not mark the prompt as human (found in the smoke test). At most 8 rounds.
- **Nudge (both arms).** If a turn ends with a question to the user, the driver replies once with:
  "Please proceed with your best judgment; I will not answer questions. Finish the task."
- At most 12 calls per build and 60 minutes per call.

## Repetitions

A pilot of one task in both arms measures cost and validates the pipeline. Pilot runs are not part of the
results. Then all 18 tasks × 2 arms × 3 repetitions = 108 builds.

## Measurements (per build)

| Metric | Source |
|---|---|
| Tokens: input, cache read, cache write, output | Transcripts, including subagents, counted once per message id; checked against the CLI JSON |
| Cost (USD, API list price) and wall time | CLI JSON (`total_cost_usd`, `duration`) |
| Calls, turns, approvals, nudges | Driver log |
| Harness runs | Bash tool calls that run `forgemyspec` |
| Model writes | Write, Edit, MultiEdit and NotebookEdit tool calls |
| Harness share | harness runs / (harness runs + model writes), the board's definition |
| Guard checks and denials | `.forgemyspec/state/ledger.jsonl` |
| Self-verification runs | Bash calls that run tests (`unittest`, `pytest`, `test`) or the program |
| Rigor reached (with arm) | Bundles: spec-only or formal; Dafny and boundary obligation counts; approved or locked |
| Framework verdict (with arm) | `gate --all` (full tier) and `risk --json`, run by the driver after the build |

## Blind judge

A third headless process (`--model claude-opus-5-5`) per task and repetition:

- It receives `A/` and `B/` in a random order (seeded). The key stays outside its directory.
- Framework artifacts are removed: `forgemyspec-bundle/`, `spec.yaml`, `*.dfy`, `planted/`, locks, `.forgemyspec/`,
  `.claude/`, `CLAUDE.md`, acceptance checklists, `evals/`, the board file and the install files (including `.gitignore`).
  Translated Dafny code (`generated/`) stays, because it is the implementation. This can unblind the judge, and
  that is measured: at the end the judge guesses which side, if any, used a spec framework, with a confidence.
- Procedure: (1) from the prompt alone, write the requirement list; (2) write black-box probes per requirement
  and run the same probes on A and B; (3) review security and code, with `ruff` and `bandit` reports precomputed
  by the driver; (4) fill `judgment.json` with the fixed schema below.
- Judge transcripts are scanned. Any access outside the judge directory invalidates that judgment, which is
  rerun.

Score per side, 0 to 5 each:

| Dimension | 5 means |
|---|---|
| Functional correctness | Every probe passes |
| Requirement coverage | Every prompt requirement met, nothing unrequested that changes behaviour |
| Security | No exploitable flaw, safe handling of input, secrets and files |
| Robustness | Invalid input and edge cases handled with clear errors and correct exit codes |
| Code quality | Clear structure, idiomatic, maintainable |
| Tests | Meaningful automated tests that pass |

Every issue is listed with severity (critical, high, medium, low) and category (functional bug, security, silent
issue, scope drift, quality). Also reported: the probe pass counts and the blinding guess.

## Analysis (fixed in advance)

- Per arm: mean and standard deviation over the 3 repetitions; per task: the paired difference (with − without).
- Over the 18 tasks: the mean paired difference with a 95% bootstrap interval (10,000 resamples, seed
  `20261031`) and a Wilcoxon signed-rank test, for issues (critical + high), probe pass rate, the overall
  score (mean of functional, coverage, security, robustness and quality; `tests` reported apart, see
  Deviation 2), tokens and cost.
- Split by complexity class as in the earlier report: simple (P03, P10, P12, P15), medium
  (P01, P06, P08, P13, P17), complex (P02, P04, P05, P11, P16), others (P07, P09, P14, P18).
- Builds that crash or time out count as delivered, with whatever exists. They are reported, never dropped.

## Known limitations

- The approver never reviews, so the value of a human reading the contract is not measured.
- One builder model (Sonnet). The judge is a model of the same family, so a shared bias is possible; blinding
  is imperfect, and its effectiveness is measured.
- Three repetitions per arm: small samples. Intervals are reported, not only means.
- P06–P15 prompts were rewritten, see above.

## Deviations

1. Pilot 1 (before the main runs) used the Homebrew `claude` 2.1.116, where the `sonnet` alias resolved to
   claude-sonnet-4-6 and the 2.1.116 CLI cannot run the 5.5 models. Fixed before any measured run: exact model
   ids and a frozen copy of Claude Code 2.1.296 (sha256 prefix c9b5341637becbd4). The pilot was rerun with the
   fixed setup. Neither pilot is part of the results.
2. The pilot judge scored `tests` 0 for a side that shipped no tests, but no prompt asks for tests. So the
   primary overall score is the mean of the other five dimensions, and the six-dimension mean and `tests` are
   reported separately. Decided after the pilot, before any measured run.
3. The pilot judge guessed the framework side from test docstrings ("obligations from spec.yaml"). Delivered
   code is not edited, so this leak stays and is measured through the blinding guess.
4. The second pilot judge guessed from `.gitignore`, which `init` writes with `.forgemyspec/` entries. `.gitignore`
   is an install file, not delivered code, so it is now removed from both sides before judging.
