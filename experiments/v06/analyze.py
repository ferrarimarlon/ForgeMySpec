"""Metrics and statistics for the v0.6 experiment, computed only from the stored evidence (PROTOCOL.md).

Usage:
  python3 experiments/v06/analyze.py            # writes results/builds.csv, results/judgments.csv, results/summary.json
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import random
import re
import statistics as st
import sys
from math import erf, sqrt
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "runs"
JUDGED = HERE / "judging"
RESULTS = HERE / "results"
SEED = 20261031
CLASSES = {"simple": ["P03", "P10", "P12", "P15"], "medium": ["P01", "P06", "P08", "P13", "P17"],
           "complex": ["P02", "P04", "P05", "P11", "P16"], "other": ["P07", "P09", "P14", "P18"]}
HARNESS = re.compile(r"-m forgemyspec\b|\bforgemyspec (lint|package|gate|risk|board|request-approval|lock|approve)")
VERIFY = re.compile(r"\b(unittest|pytest|python3?\s+\S+\.py|python3?\s+-m\s|python3?\s+-c|make\b|qemu|dafny|"
                    r"node\s|curl\s|bash\s+\S+\.sh|\./\S+)")
WRITES = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# Primary score: no prompt asks for tests, so `tests` is reported apart (Deviation 2).
PRIMARY = ("functional", "coverage", "security", "robustness", "quality")


def klass(task: str) -> str:
    return next(k for k, v in CLASSES.items() if task[:3] in v)


def transcript_metrics(logs: Path) -> dict:
    usage, tools = {}, {}
    for f in sorted(logs.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", errors="replace") as h:
            for line in h:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("type") != "assistant":
                    continue
                m = e.get("message") or {}
                if m.get("usage"):
                    usage[(f.name, m.get("id"))] = m["usage"]
                for b in m.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tools[b.get("id")] = (b.get("name"), (b.get("input") or {}).get("command") or "")
    tok = {k: sum(int(u.get(k) or 0) for u in usage.values())
           for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")}
    harness = sum(1 for n, c in tools.values() if n == "Bash" and HARNESS.search(c))
    writes = sum(1 for n, _ in tools.values() if n in WRITES)
    verify = sum(1 for n, c in tools.values() if n == "Bash" and not HARNESS.search(c) and VERIFY.search(c))
    bash = sum(1 for n, _ in tools.values() if n == "Bash")
    return {**tok, "tokens_total": sum(tok.values()), "api_calls": len(usage), "tool_calls": len(tools),
            "harness_runs": harness, "model_writes": writes, "verify_runs": verify, "other_bash": bash - harness - verify,
            "harness_share": round(harness / (harness + writes), 3) if harness + writes else 0.0,
            "subagents": len(list(logs.glob("subagent-*.gz")))}


def rigor(code: Path, logs: Path) -> dict:
    specs = [p for p in code.rglob("spec.yaml") if ".forgemyspec" not in p.parts]
    formal = spec_only = dafny = boundary = approved = 0
    for s in specs:
        try:
            data = yaml.safe_load(s.read_text()) or {}
        except Exception:
            continue
        obl = ((data.get("formal") or {}).get("obligations")) or []
        dafny += sum(1 for o in obl if isinstance(o, dict) and o.get("kind") == "dafny")
        boundary += sum(1 for o in obl if isinstance(o, dict) and o.get("kind") == "boundary")
        if (s.parent / "contract.dfy").exists():
            formal += 1
            approved += (s.parent / "contract.lock").exists()
        else:
            spec_only += 1
            approved += (s.parent / "spec.lock").exists()
    ledger = logs / "forgemyspec-state" / "ledger.jsonl"
    checks = denies = 0
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "pre-tool-use":
                checks += 1
                denies += e.get("decision") == "deny"
    gate_txt = (logs / "final-gate.txt").read_text() if (logs / "final-gate.txt").exists() else ""
    level = "formal" if formal else ("spec-only" if spec_only else "none")
    return {"rigor": level, "bundles": len(specs), "dafny_obligations": dafny, "boundary_obligations": boundary,
            "bundles_approved": approved, "guard_checks": checks, "guard_denials": denies,
            "final_gate": "PASS" if "RESULT: PASS" in gate_txt and "RESULT: FAIL" not in gate_txt
            else ("FAIL" if "RESULT: FAIL" in gate_txt else ("none" if gate_txt else ""))}


def builds() -> list:
    rows = []
    for meta_path in sorted(OUT.glob("*/*/logs/meta.json")):
        logs = meta_path.parent
        meta = json.loads(meta_path.read_text())
        if meta["rep"] == 0 and not os.environ.get("INCLUDE_PILOT"):  # pilot, excluded by protocol
            continue
        calls = meta["calls"]
        models = sorted({m for c in calls for m in (c.get("modelUsage") or {})})
        row = {"task": meta["task"], "class": klass(meta["task"]), "arm": meta["arm"], "rep": meta["rep"],
               "models": "+".join(models), "calls": len(calls), "turns": sum(c.get("num_turns") or 0 for c in calls),
               "cost_usd": round(sum(c.get("cost_usd") or 0 for c in calls), 4),
               "wall_min": round(sum(c.get("wall_s") or 0 for c in calls) / 60, 1),
               "approvals": len(meta["approvals"]), "nudges": meta["nudges"],
               "errors": sum(1 for c in calls if c.get("is_error") or c.get("exit") != 0)}
        row.update(transcript_metrics(logs))
        row.update(rigor(logs.parent / "code", logs) if meta["arm"] == "with" else
                   {"rigor": "n/a", "final_gate": "n/a"})
        rows.append(row)
    return rows


def judgments() -> list:
    rows = []
    for key_path in sorted(JUDGED.glob("*/key.json")):
        key = json.loads(key_path.read_text())
        task, rep = key_path.parent.name.rsplit("-r", 1)
        if rep == "0" and not os.environ.get("INCLUDE_PILOT"):  # pilot, excluded by protocol
            continue
        if not key.get("valid"):
            continue
        j = json.loads((key_path.parent / "judgment.json").read_text())
        guess = (j.get("blinding_guess") or {})
        truth = next(s for s, a in key["key"].items() if a == "with")
        for side, arm in key["key"].items():
            s = j.get(side) or {}
            issues = s.get("issues") or []
            sev = {k: sum(1 for i in issues if i.get("severity") == k) for k in ("critical", "high", "medium", "low")}
            cat = {k: sum(1 for i in issues if i.get("category") == k) for k in ("functional", "security", "silent",
                                                                               "scope", "quality")}
            scores = s.get("scores") or {}
            probes = j.get("probes_total") or 0
            rows.append({"task": task, "class": klass(task), "rep": int(rep), "arm": arm, "side": side,
                         **{f"score_{k}": scores.get(k) for k in ("functional", "coverage", "security", "robustness",
                                                                  "quality", "tests")},
                         "score_mean": round(st.mean(scores[k] for k in PRIMARY if isinstance(scores.get(k), (int, float))), 3)
                         if scores and any(isinstance(scores.get(k), (int, float)) for k in PRIMARY) else None,
                         "score_mean6": round(st.mean(v for v in scores.values() if isinstance(v, (int, float))), 3)
                         if scores else None,
                         "probes_total": probes, "probes_passed": s.get("probes_passed"),
                         "probe_rate": round((s.get("probes_passed") or 0) / probes, 3) if probes else None,
                         "req_met": s.get("requirements_met"), "req_missing": s.get("requirements_missing"),
                         **{f"sev_{k}": v for k, v in sev.items()}, **{f"cat_{k}": v for k, v in cat.items()},
                         "crit_high": sev["critical"] + sev["high"], "issues": len(issues), "loc": s.get("loc"),
                         "guess_side": guess.get("spec_framework_side"), "guess_conf": guess.get("confidence"),
                         "guess_correct": guess.get("spec_framework_side") == truth})
    return rows


def bootstrap_ci(diffs: list, n: int = 10000) -> tuple:
    rng = random.Random(SEED)
    means = sorted(st.mean(rng.choice(diffs) for _ in diffs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def wilcoxon(diffs: list) -> float:
    """Two-sided Wilcoxon signed-rank p-value, normal approximation with tie correction (zeros dropped)."""
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n < 1:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    ties = 0.0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    w = sum(r for r, x in zip(ranks, d) if x > 0)
    mu = n * (n + 1) / 4
    sigma = sqrt(n * (n + 1) * (2 * n + 1) / 24 - ties / 48)
    if sigma == 0:
        return 1.0
    z = (w - mu - (0.5 if w > mu else -0.5 if w < mu else 0)) / sigma
    return round(2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2)))), 4)


def paired(rows: list, metric: str) -> dict:
    per = {}
    for r in rows:
        v = r.get(metric)
        if isinstance(v, (int, float)):
            per.setdefault(r["task"], {}).setdefault(r["arm"], []).append(v)
    diffs, w, wo = [], [], []
    for task, arms in sorted(per.items()):
        if arms.get("with") and arms.get("without"):
            a, b = st.mean(arms["with"]), st.mean(arms["without"])
            w.append(a)
            wo.append(b)
            diffs.append(a - b)
    if not diffs:
        return {}
    lo, hi = bootstrap_ci(diffs)
    return {"tasks": len(diffs), "with_mean": round(st.mean(w), 4), "without_mean": round(st.mean(wo), 4),
            "diff_mean": round(st.mean(diffs), 4), "ci95": [round(lo, 4), round(hi, 4)], "wilcoxon_p": wilcoxon(diffs)}


def write_csv(path: Path, rows: list) -> None:
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as h:
        w = csv.DictWriter(h, keys)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    b, j = builds(), judgments()
    write_csv(RESULTS / "builds.csv", b)
    write_csv(RESULTS / "judgments.csv", j)
    summary = {"builds": len(b), "judged_pairs": len(j) // 2,
               "build_metrics": {m: paired(b, m) for m in ("tokens_total", "output_tokens", "input_tokens",
                                                            "cache_read_input_tokens", "cache_creation_input_tokens",
                                                            "cost_usd", "wall_min", "api_calls", "model_writes",
                                                            "harness_runs", "verify_runs")},
               "judge_metrics": {m: paired(j, m) for m in ("score_mean", "score_mean6", "score_functional", "score_coverage",
                                                            "score_security", "score_robustness", "score_quality",
                                                            "score_tests", "probe_rate", "crit_high", "issues",
                                                            "sev_critical", "sev_high", "cat_security", "cat_silent",
                                                            "cat_scope", "cat_functional", "loc")},
               "by_class": {c: {m: paired([r for r in j if r["class"] == c], m)
                                for m in ("score_mean", "probe_rate", "crit_high")} for c in CLASSES},
               "by_class_cost": {c: paired([r for r in b if r["class"] == c], "cost_usd") for c in CLASSES},
               "rigor": {r["task"] + f"-r{r['rep']}": r["rigor"] for r in b if r["arm"] == "with"},
               "final_gate": {r["task"] + f"-r{r['rep']}": r["final_gate"] for r in b if r["arm"] == "with"},
               "harness_share_with": round(st.mean([r["harness_share"] for r in b if r["arm"] == "with"]), 3)
               if any(r["arm"] == "with" for r in b) else None,
               "blinding": {"guesses": len(j) // 2,
                            "correct": sum(1 for r in j if r["arm"] == "with" and r["guess_correct"]),
                            "unsure_or_neither": sum(1 for r in j if r["arm"] == "with"
                                                     and r["guess_side"] in ("unsure", "neither"))}}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
