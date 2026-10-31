# ForgeMySpec v0.6 experiment: report

Protocol: [PROTOCOL.md](PROTOCOL.md), pre-registered in commit `5329041`, with deviations 1–4 logged before any
measured run (`ab9be59`). Raw evidence: [`runs/`](runs) (code, CLI JSON, transcripts, guard ledgers) and
[`judging/`](judging) (blind judgments, probes, static reports, the A/B key). Tables: [`results/`](results).
Recompute everything with `python3 experiments/v06/analyze.py`.

## Setup in one paragraph

18 tasks: the 17 benchmark projects and the mini-OS. Each was built 3 times without and 3 times with ForgeMySpec,
108 builds in all. Every build was a separate headless Claude Code 2.1.296 process on `claude-sonnet-5-5`, in an
empty folder with no user settings, MCP or memory. In the with arm, an automatic approver approved the first
proposal unchanged. A blind judge (`claude-opus-5-5`) received each pair as A/B, with the framework files
removed. It wrote black-box probes from the prompt alone and scored 6 dimensions. Total spend: **$53.24** at API
list price ($29.83 builds, $23.41 judges).

## Results

### 1. Cost: the framework costs about 5× more per task

| Per build (mean of 54) | without | with | ratio | 95% CI of the difference | p (Wilcoxon) |
|---|---:|---:|---:|---|---:|
| Cost (USD) | 0.094 | 0.458 | **4.9×** | +0.32 to +0.42 | 0.0002 |
| Tokens, all kinds | 60,234 | 396,889 | 6.6× | +307k to +371k | 0.0002 |
| Output tokens | 4,659 | 14,670 | 3.1× | +8.9k to +11.0k | 0.0002 |
| API calls | 3.1 | 13.9 | 4.5× | | 0.0002 |
| Wall time (min) | 0.6 | 1.7 | 2.7× | | 0.0002 |

The ratio barely moves with complexity: 5.8× for simple tasks, 4.8× medium, 4.2× complex, 5.3× others. Most of
the extra tokens are context re-read on every call (cache reads: 355k against 45k). The framework's skills,
CLAUDE.md, spec and board travel with every turn.

### 2. Quality and security: no measurable gain

**Primary analysis** (as pre-registered: every build counts, including empty ones):

| Blind judge, per build | without | with | difference (95% CI) | p |
|---|---:|---:|---|---:|
| Overall score (5 dimensions, 0–5) | **4.34** | 4.04 | −0.30 (−0.59 to −0.02) | 0.058 |
| Functional | 4.48 | 4.00 | −0.48 (−0.91 to −0.04) | 0.047 |
| Black-box probes passed | 94.9% | 88.5% | −6.4 pp (−12.2 to −1.2) | 0.080 |
| Security | 4.81 | 4.50 | −0.31 (−0.70 to +0.04) | 0.148 |
| Critical + high issues | 0.056 | 0.093 | +0.04 (−0.04 to +0.13) | 0.484 |
| Tests (no prompt asks for them) | 0.00 | 3.74 | +3.74 | 0.0002 |

The with arm's deficit comes entirely from **4 of its 54 builds that delivered nothing** (P06 r1, P07 r1, P11 r1,
P13 r2). In each one, Claude wrote and packaged the spec and then ended the turn by *asking the user* to run
`request-approval`, or by saying it would run it, without ever running it. No code existed, so the automatic
approver had nothing to approve, and the message did not end in a question, so the single nudge did not fire.
These are real failures of the framework's approval handoff in autonomous use. A person at the keyboard would
have unblocked them with one message.

**Sensitivity analysis** (post hoc, labelled as such: the 4 empty builds excluded):

| | without | with | difference (95% CI) | p |
|---|---:|---:|---|---:|
| Overall score | 4.34 | 4.37 | +0.03 (−0.12 to +0.19) | 0.92 |
| Functional | 4.48 | 4.33 | −0.15 (−0.52 to +0.22) | 0.39 |
| Probes passed | 94.9% | 95.8% | +0.9 pp (−1.2 to +2.9) | 0.51 |
| Security | 4.81 | 4.86 | +0.05 (−0.08 to +0.20) | 0.58 |
| Robustness | 3.59 | 3.92 | +0.32 (−0.10 to +0.77) | 0.19 |
| Critical + high issues | 0.056 | 0.019 | −0.04 (−0.11 to +0.04) | 0.42 |
| Silent issues | 0.52 | 0.81 | +0.29 (−0.14 to +0.69) | 0.15 |

When the framework does deliver, the code is **statistically indistinguishable** from plain Claude Code in
correctness, coverage, security and quality. It ships tests, and robustness trends higher but is not
significant. The earlier benchmark's headline (8 issues against 16, 0 vulnerabilities against 1) **does not
reproduce** with today's model and today's framework.

Security across all 108 builds: the judge found **no critical or high security flaw in either arm**. Lower
findings: with 2 medium and 5 low, without 4 medium and 2 low. Examples on both sides: a hard-coded fallback API
key in P02, argv echo of secret fragments in P16, an unvalidated note id in P05 (without), and `list` revealing
values of 4 characters or fewer in P16 (with). No P04 build in either arm used `eval()`, the flaw the earlier
benchmark found without a spec.

### 3. Harness against model

| With arm, per build | mean |
|---|---:|
| Harness runs (`forgemyspec` lint, package, gate, board…) | 6.8 |
| Model writes (Write/Edit) | 3.4 |
| **Harness share** (runs / (runs + writes)) | **70%** |
| Guard checks recorded in the ledger | 12.2 (1.8 denied) |
| Self-run tests or program executions outside the harness | 0.7 (without arm: 1.3) |

The harness does most of the checking, and it partly replaces the model's own habit of running the program:
the without arm executed its code more often.

### 4. Rigor the framework chose

**54 of 54 with-arm builds were spec-only.** The framework never chose a formal Dafny bundle: not for the secret
vault, not for the money tasks (P06, P11, P14), not for the OS. In P06 r1 it offered Dafny "because this handles
money" and left the choice to the user. The final full gate (run by the driver afterwards) passed in **50 of 54**
builds; the other 4 are the empty ones. With the default skill, the formal layer that sets ForgeMySpec apart is
effectively unused unless the user asks for it.

### 5. Per task (overall score with/without, probes with/without, cost with/without)

| Task | Score | Probes | Cost |
|---|---|---|---|
| P01 task manager | 4.33 / 4.47 | 0.97 / 0.96 | $0.46 / $0.09 |
| P02 blog API | 4.47 / 4.13 | 0.99 / 0.96 | $0.51 / $0.09 |
| P03 dir organizer | 3.87 / 4.13 | 0.92 / 0.94 | $0.45 / $0.06 |
| P04 CSV analytics | 4.00 / 4.60 | 0.92 / 1.00 | $0.39 / $0.08 |
| P05 note taker | 4.13 / 4.40 | 0.91 / 0.95 | $0.50 / $0.10 |
| P06 expense splitter ¹ | 3.07 / 4.33 | 0.67 / 0.94 | $0.37 / $0.08 |
| P07 password checker ¹ | 2.80 / 4.07 | 0.66 / 0.94 | $0.40 / $0.10 |
| P08 time tracker | 4.47 / 4.40 | 0.96 / 0.96 | $0.43 / $0.07 |
| P09 cron parser | 4.73 / 3.93 | 1.00 / 0.92 | $0.77 / $0.09 |
| P10 data dedup | 4.27 / 4.47 | 0.92 / 0.92 | $0.40 / $0.06 |
| P11 invoice generator ¹ | 2.93 / 4.40 | 0.64 / 0.94 | $0.28 / $0.12 |
| P12 config validator | 4.20 / 4.20 | 0.91 / 0.92 | $0.37 / $0.07 |
| P13 state machine ¹ | 3.13 / 4.33 | 0.65 / 0.91 | $0.33 / $0.09 |
| P14 budget tracker | 4.13 / 4.20 | 0.93 / 0.93 | $0.41 / $0.08 |
| P15 grade calculator | 4.73 / 4.13 | 1.00 / 0.91 | $0.45 / $0.09 |
| P16 secret vault | 4.20 / 4.53 | 0.97 / 0.98 | $0.69 / $0.18 |
| P17 job scheduler | 4.60 / 4.67 | 0.97 / 0.99 | $0.51 / $0.11 |
| P18 mini-OS | 4.60 / 4.67 | 0.94 / 1.00 | $0.52 / $0.14 |

¹ One of three with-arm builds delivered nothing (approval handoff stalled).

The framework did best on P09 (cron parser) and P15 (grade calculator). Both have dense edge-case rules (invalid
dates, weight normalization) that the spec forced it to pin down.

## Validity

- **Blinding was partial.** The judge guessed the framework side correctly in 31 of 54 pairs and was unsure in
  23. It never guessed wrong. The giveaway was the with arm's test files, which name obligations. A judge that
  knows may favour or penalize; the security and probe results are less exposed to this than the 0–5 scores.
- Judge transcripts were audited for access outside their folder: 0 hits. All 54 judgments were valid on the
  first attempt.
- The approver never reviews. The benefit of a human reading the spec is not measured, and neither is the
  benefit of a human unblocking a stalled handoff.
- One builder model (Sonnet 5.5) and one judge family (Opus 5.5). 3 repetitions per task. P06–P15 prompts were
  rewritten from summaries (PROTOCOL.md).
- Cost is API list price as reported by the CLI. On a subscription the same work consumes the usage limit
  in proportion.

## What this means for ForgeMySpec

1. **The approval handoff breaks without a human.** Sometimes Claude tells the user to run `request-approval`
   instead of running it. The skill must make running it mandatory, and the Stop hook could block a turn that
   ends with a spec but no pending request. 7% of with-arm builds died at this step.
2. **Spec-only adds cost, not quality**, for tasks of this size with today's model: 4.9× the cost, the same
   correctness and security, plus a test suite. The test suite is the one clear deliverable gain.
3. **The formal layer is never reached by default.** If Dafny proofs are the point, the default skill's
   "spec-only unless critical" rule has to be revisited, or money and security tasks should trigger a formal
   proposal that the user must answer.
4. **Most of the overhead is context re-read on every call.** Smaller skills, a smaller CLAUDE.md block and a
   shorter board would cut the 6.6× token ratio directly. This is backlog R38: cost per requirement.
