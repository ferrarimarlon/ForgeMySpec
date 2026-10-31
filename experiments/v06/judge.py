"""Blind judge for the v0.6 experiment (see PROTOCOL.md, "Blind judge").

Usage:
  python3 experiments/v06/judge.py one P17-job-scheduler 1
  python3 experiments/v06/judge.py all --reps 1 2 3 --workers 3
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import CLAUDE_BIN, OUT, TASKS, TMP, clean_env, now, transcripts  # noqa: E402

HERE = Path(__file__).resolve().parent
JUDGED = HERE / "judging"
TOOLS = TMP / "tools" / "bin"
SEED = 20261031
STRIP_DIRS = {"forgemyspec-bundle", "planted", ".forgemyspec", ".claude", "evals", ".githooks", ".github"}
STRIP_FILES = {"spec.yaml", "CLAUDE.md", "acceptance-checklist.md", "forgemyspec-board.yaml", "contract.lock",
               "spec.lock", "implement-from-spec.md", ".gitignore"}
STRIP_SUFFIXES = {".dfy"}
FORBIDDEN = ("Desktop/ForgeMySpec", "fms-v06/runs", "fms-v06/logs", "judging/key")

RUBRIC = """You are an independent senior reviewer judging two implementations, A and B, of the same task. You do not
know how either was produced. Judge only what is in A/ and B/ in this directory.

Rules:
- Never read, list or search anything outside this directory (no parent directories, no home directory
  except what the task's program itself uses at runtime). Doing so invalidates your work.
- Treat A and B exactly the same way: the same probes, the same scrutiny, in the order A then B.

Procedure:
1. Read TASK.md only. Write requirements.json: a numbered list of every requirement stated or clearly implied by
   the task (id, text). Do this before opening A/ or B/.
2. Write black-box probes that check those requirements through each program's public interface (CLI, HTTP,
   files, boot output). Put them in probes/. Adapt only the invocation to each side's interface, never the
   expectation. Run every probe on A and on B, and save the results in probes/results.json as
   {"A": {"<probe id>": "pass"|"fail", ...}, "B": {...}}. Use temporary directories; if the program writes under
   the home directory, use and clean only the paths the task names.
3. Review the code of each side for security and quality. static/ holds precomputed ruff and bandit reports.
   Run each side's own tests, if any.
4. Write judgment.json with exactly this schema:
{
 "requirements_total": int,
 "probes_total": int,
 "A": {"probes_passed": int,
       "scores": {"functional": 0-5, "coverage": 0-5, "security": 0-5, "robustness": 0-5, "quality": 0-5, "tests": 0-5},
       "requirements_met": int, "requirements_partial": int, "requirements_missing": int,
       "issues": [{"severity": "critical|high|medium|low",
                   "category": "functional|security|silent|scope|quality",
                   "requirement": "<id or null>", "evidence": "<probe id, file:line or command output>",
                   "summary": "<one sentence>"}],
       "own_tests": {"present": bool, "ran": bool, "passed": int, "failed": int},
       "loc": int},
 "B": { ...same... },
 "blinding_guess": {"spec_framework_side": "A|B|neither|unsure", "confidence": 0-1, "why": "<one sentence>"},
 "notes": "<anything a reader needs, max 5 sentences>"
}
Scoring anchors: 5 = no issue in that dimension; 4 = only low issues; 3 = a medium issue; 2 = a high issue;
1 = several high or one critical; 0 = absent or does not run. "silent" = wrong behaviour without a crash or error.
"scope" = a requirement missing, or unrequested behaviour that changes what the user gets.
Every issue needs evidence you produced. Do not guess. Finish by printing the judgment."""


def strip(src: Path, dst: Path) -> None:
    def ignore(d, names):
        out = []
        for n in names:
            p = Path(d) / n
            if n in STRIP_DIRS or n in STRIP_FILES or p.suffix in STRIP_SUFFIXES or n in {".git", "__pycache__"}:
                out.append(n)
        return out
    shutil.copytree(src, dst, ignore=ignore, symlinks=False)


def sanitize(side_dir: Path, task: str, arm: str, rep: int) -> int:
    """Replaces the build's absolute path (which names the arm) with a neutral one in every text file."""
    roots = [str(TMP / "runs" / task / f"{arm}-r{rep}"), str(TMP / "runs" / task).replace("/private", "", 1)
             + f"/{arm}-r{rep}"]
    changed = 0
    for p in side_dir.rglob("*"):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = text
        for r in roots:
            new = new.replace(r, "/project")
        if new != text:
            p.write_text(new, encoding="utf-8")
            changed += 1
    return changed


def static_reports(jdir: Path) -> None:
    (jdir / "static").mkdir()
    for side in ("A", "B"):
        r = subprocess.run(["ruff", "check", "--no-cache", "--isolated", "--select", "E,F,W,B,S,UP,C90",
                            "--output-format", "concise", "."], cwd=jdir / side, capture_output=True, text=True)
        (jdir / "static" / f"{side}-ruff.txt").write_text(r.stdout + r.stderr)
        r = subprocess.run([str(TOOLS / "bandit"), "-r", ".", "-q", "-f", "txt"], cwd=jdir / side,
                           capture_output=True, text=True)
        (jdir / "static" / f"{side}-bandit.txt").write_text(r.stdout + r.stderr)


def audit(sid: str) -> list:
    hits = []
    for t in transcripts(sid):
        text = t.read_text(errors="replace")
        hits += [f for f in FORBIDDEN if f in text]
    return sorted(set(hits))


def judge(task: str, rep: int, attempt: int = 1) -> dict:
    rng = random.Random(f"{SEED}-{task}-{rep}")
    arms = ["without", "with"]
    rng.shuffle(arms)
    key = {"A": arms[0], "B": arms[1]}
    jdir = TMP / "judge" / f"{task}-r{rep}"
    shutil.rmtree(jdir, ignore_errors=True)
    jdir.mkdir(parents=True)
    (jdir / "TASK.md").write_text((TASKS / f"{task}.md").read_text())
    for side, arm in key.items():
        strip(OUT / task / f"{arm}-r{rep}" / "code", jdir / side)
        sanitize(jdir / side, task, arm, rep)
    static_reports(jdir)
    subprocess.run(["git", "init", "-q"], cwd=jdir)

    import uuid
    sid = str(uuid.uuid4())
    cmd = [CLAUDE_BIN, "-p", RUBRIC, "--model", "claude-opus-5-5", "--permission-mode", "bypassPermissions",
           "--setting-sources", "local", "--strict-mcp-config", "--output-format", "json", "--session-id", sid]
    p = subprocess.run(cmd, cwd=jdir, env=clean_env(), capture_output=True, text=True, timeout=3 * 3600,
                       stdin=subprocess.DEVNULL)
    dest = JUDGED / f"{task}-r{rep}"
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    (dest / "cli.json").write_text(p.stdout)
    for name in ("judgment.json", "requirements.json"):
        if (jdir / name).exists():
            shutil.copy(jdir / name, dest / name)
    if (jdir / "probes").exists():
        shutil.copytree(jdir / "probes", dest / "probes", dirs_exist_ok=True)
    shutil.copytree(jdir / "static", dest / "static", dirs_exist_ok=True)
    for t in transcripts(sid):
        with open(t, "rb") as s, gzip.open(dest / f"{t.name}.gz", "wb") as d:
            shutil.copyfileobj(s, d)
    hits = audit(sid)
    valid = (dest / "judgment.json").exists() and not hits
    try:
        json.loads((dest / "judgment.json").read_text())
    except Exception:
        valid = False
    (dest / "key.json").write_text(json.dumps({"key": key, "session_id": sid, "audit_hits": hits, "valid": valid,
                                               "attempt": attempt, "at": now()}, indent=1))
    if not valid and attempt < 2:
        return judge(task, rep, attempt + 1)
    return {"task": task, "rep": rep, "valid": valid, "audit_hits": hits}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("one")
    o.add_argument("task")
    o.add_argument("rep", type=int)
    a = sub.add_parser("all")
    a.add_argument("--reps", type=int, nargs="+", default=[1, 2, 3])
    a.add_argument("--workers", type=int, default=3)
    a.add_argument("--tasks", nargs="*")
    args = ap.parse_args()
    if args.cmd == "one":
        print(json.dumps(judge(args.task, args.rep)))
        return 0
    tasks = args.tasks or sorted(p.stem for p in TASKS.glob("*.md"))

    def group(task):  # judges of one task never overlap (ports, home paths)
        res = []
        for rep in args.reps:
            if (JUDGED / f"{task}-r{rep}" / "key.json").exists():
                continue
            if all((OUT / task / f"{arm}-r{rep}" / "logs" / "meta.json").exists() for arm in ("with", "without")):
                r = judge(task, rep)
                print(json.dumps(r), flush=True)
                res.append(r)
        return res
    with cf.ThreadPoolExecutor(args.workers) as pool:
        for f in cf.as_completed([pool.submit(group, t) for t in tasks]):
            f.result()
    return 0


if __name__ == "__main__":
    sys.exit(main())
