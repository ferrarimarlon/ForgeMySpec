"""ForgeMySpec v0.6 experiment driver: builds every task twice (without / with the framework) in isolated,
headless Claude Code processes, and keeps the raw evidence (CLI JSON, transcripts, ledger, final tree).

Usage:
  python3 experiments/v06/run.py build P17-job-scheduler without 1
  python3 experiments/v06/run.py all --reps 1 2 3 --workers 3 [--tasks P01-task-manager ...]

Protocol: experiments/v06/PROTOCOL.md. Nothing here reads results to decide what to do next, except the
automatic approver (with arm) and the single symmetric nudge (both arms), both written down in the protocol.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
OUT = HERE / "runs"
TMP = Path("/private/tmp/fms-v06")
MODEL = "claude-sonnet-5-5"
# Frozen copy of Claude Code 2.1.296 (sha256 c9b5341637becbd4…); the Homebrew 2.1.116 cannot run the 5.5 models.
CLAUDE_BIN = str(TMP / "tools" / "claude")
CALL_TIMEOUT = 60 * 60          # one claude -p call
MAX_CALLS = 12                  # per build
MAX_APPROVALS = 8               # approver rounds per build (with arm)
NUDGE = "Please proceed with your best judgment; I will not answer questions. Finish the task."
# Tasks whose program writes under the home directory: wiped before each run so runs cannot see each other.
HOME_PATHS = {"P05-note-taker": ["~/.note-taker"], "P16-secret-vault": ["~/.vault"]}
EXCLUDE = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}
INSTALL_ONLY = [".forgemyspec/harness", ".claude/skills", ".claude/agents", ".githooks", ".github"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def clean_env() -> dict:
    """No variable of the parent Claude Code session reaches the builder."""
    return {k: v for k, v in os.environ.items()
            if not k.startswith("CLAUDE") and k not in ("PYTHONPATH", "VIRTUAL_ENV")}


def tty(cmd: list, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    """Runs a command under a pseudo-terminal: the harness counts that as the user approving in a terminal."""
    return subprocess.run(["script", "-q", "/dev/null"] + cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=900)


def claude(root: Path, message: str, sid: str, resume: bool, logdir: Path, n: int) -> dict:
    cmd = [CLAUDE_BIN, "-p", message, "--model", MODEL, "--permission-mode", "bypassPermissions",
           "--setting-sources", "project,local", "--strict-mcp-config", "--output-format", "json"]
    cmd += ["-r", sid] if resume else ["--session-id", sid]
    started = time.time()
    try:
        p = subprocess.run(cmd, cwd=root, env=clean_env(), capture_output=True, text=True, timeout=CALL_TIMEOUT,
                           stdin=subprocess.DEVNULL)
        stdout, stderr, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "TIMEOUT", -1
    (logdir / f"call{n:02d}.json").write_text(stdout)
    (logdir / f"call{n:02d}.err").write_text(stderr or "")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        data = {"subtype": "unparsable", "result": stdout[-2000:]}
    return {"n": n, "message": message, "exit": code, "wall_s": round(time.time() - started, 1),
            "subtype": data.get("subtype"), "is_error": data.get("is_error"), "num_turns": data.get("num_turns"),
            "cost_usd": data.get("total_cost_usd"), "usage": data.get("usage"), "modelUsage": data.get("modelUsage"),
            "result": data.get("result")}


def new_requests(root: Path, since: str) -> list:
    path = root / ".forgemyspec" / "state" / "approvals.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    items = []
    for r in data.get("requests", []):
        if str(r.get("created_at", "")) >= since:
            for i in r.get("items", []):
                if not i.get("used_at") and (i["action"], i["target"]) not in items:
                    items.append((i["action"], i["target"]))
    return items


def asks_question(text: str) -> bool:
    lines = [l.strip() for l in (text or "").strip().splitlines() if l.strip()]
    return bool(lines) and lines[-1].rstrip("*_` ").endswith("?")


def copy_tree(src: Path, dst: Path, skip_install: bool) -> None:
    skip = {src / s for s in INSTALL_ONLY} if skip_install else set()

    def ignore(d, names):
        return [n for n in names if n in EXCLUDE or Path(d) / n in skip]
    shutil.copytree(src, dst, ignore=ignore, symlinks=True, dirs_exist_ok=True)


def transcripts(sid: str) -> list:
    base = Path.home() / ".claude" / "projects"
    found = list(base.glob(f"*/{sid}.jsonl")) + list(base.glob(f"*/{sid}/subagents/*.jsonl"))
    return sorted(set(found))


def build(task: str, arm: str, rep: int) -> dict:
    assert arm in ("without", "with")
    prompt = (TASKS / f"{task}.md").read_text().strip()
    run = f"{arm}-r{rep}"
    root = TMP / "runs" / task / run
    logdir = TMP / "logs" / task / run
    dest = OUT / task / run
    for d in (root, logdir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    for p in HOME_PATHS.get(task, []):
        shutil.rmtree(Path(p).expanduser(), ignore_errors=True)
    env = clean_env()
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, env=env)
    git("init", "-q")
    git("config", "user.email", "builder@experiment.local")
    git("config", "user.name", "builder")
    if arm == "with":
        r = tty(["env", f"PYTHONPATH={REPO / 'src'}", "python3", "-m", "forgemyspec", "init", "."], root, env)
        (logdir / "init.txt").write_text(r.stdout + r.stderr)
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", "baseline")

    sid = str(uuid.uuid4())
    meta = {"task": task, "arm": arm, "rep": rep, "model_alias": MODEL, "session_id": sid, "root": str(root),
            "started": now(), "calls": [], "approvals": [], "nudges": 0, "refused": []}
    message, resume = prompt, False
    while len(meta["calls"]) < MAX_CALLS:
        since = now()
        call = claude(root, message, sid, resume, logdir, len(meta["calls"]) + 1)
        meta["calls"].append(call)
        resume = True
        if call["exit"] != 0 and call["subtype"] in (None, "unparsable"):
            break
        pending = new_requests(root, since) if arm == "with" else []
        if pending and len(meta["approvals"]) < MAX_APPROVALS:
            reports = []
            for action, target in pending:
                if action in ("init", "suspend"):
                    meta["refused"].append([action, target])
                    reports.append(f"I did not run `forgemyspec {action} {target}`: that is not part of this task.")
                    continue
                r = tty(["env", f"PYTHONPATH={root / '.forgemyspec' / 'harness'}", "python3", "-m", "forgemyspec",
                         action, target], root, env)
                out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]|\r", "", r.stdout + r.stderr).strip().splitlines()[-15:]
                meta["approvals"].append({"action": action, "target": target, "exit": r.returncode, "at": now()})
                reports.append(f"I ran `forgemyspec {action} {target}` in my own terminal (exit {r.returncode}):\n"
                               "```\n" + "\n".join(out) + "\n```")
            message = "Approved.\n\n" + "\n\n".join(reports)
            continue
        if meta["nudges"] < 1 and asks_question(call["result"]):
            meta["nudges"] += 1
            message = NUDGE
            continue
        break
    meta["ended"] = now()

    # Measurement after the build (not part of it): the framework's own verdict, run by the driver.
    if arm == "with":
        h = {**env, "PYTHONPATH": str(root / ".forgemyspec" / "harness")}
        for name, args in (("gate", ["gate", "--all"]), ("risk", ["risk", "--json"])):
            try:
                r = subprocess.run([sys.executable, "-m", "forgemyspec", *args], cwd=root, env=h, capture_output=True,
                                   text=True, timeout=3600)
                (logdir / f"final-{name}.txt").write_text(r.stdout + r.stderr)
                meta[f"final_{name}_exit"] = r.returncode
            except subprocess.TimeoutExpired:
                meta[f"final_{name}_exit"] = "timeout"
    (logdir / "diffstat.txt").write_text(git("add", "-A").stdout + git("diff", "--cached", "--stat", "HEAD").stdout)

    for t in transcripts(sid):
        name = t.name if t.parent.name != "subagents" else f"subagent-{t.name}"
        with open(t, "rb") as src, gzip.open(logdir / f"{name}.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
    state = root / ".forgemyspec" / "state"
    if state.exists():
        shutil.copytree(state, logdir / "forgemyspec-state", dirs_exist_ok=True)
    for p in HOME_PATHS.get(task, []):
        hp = Path(p).expanduser()
        if hp.exists():
            shutil.copytree(hp, logdir / "home" / hp.name, dirs_exist_ok=True)
            shutil.rmtree(hp, ignore_errors=True)
    (logdir / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    shutil.rmtree(dest, ignore_errors=True)
    copy_tree(root, dest / "code", skip_install=True)
    shutil.copytree(logdir, dest / "logs", dirs_exist_ok=True)
    return {"task": task, "run": run, "calls": len(meta["calls"]),
            "cost": round(sum(c.get("cost_usd") or 0 for c in meta["calls"]), 3)}


def task_group(task: str, reps: list, seed: int) -> list:
    """All runs of one task, one after the other (shared ports and home paths); arm order shuffled per rep."""
    rng = random.Random(f"{seed}-{task}")
    done = []
    for rep in reps:
        arms = ["without", "with"]
        rng.shuffle(arms)
        for arm in arms:
            if (OUT / task / f"{arm}-r{rep}" / "logs" / "meta.json").exists():
                continue
            res = build(task, arm, rep)
            print(json.dumps(res), flush=True)
            done.append(res)
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("task")
    b.add_argument("arm")
    b.add_argument("rep", type=int)
    a = sub.add_parser("all")
    a.add_argument("--reps", type=int, nargs="+", default=[1])
    a.add_argument("--workers", type=int, default=3)
    a.add_argument("--tasks", nargs="*")
    a.add_argument("--seed", type=int, default=20261031)
    args = ap.parse_args()
    if args.cmd == "build":
        print(json.dumps(build(args.task, args.arm, args.rep)))
        return 0
    tasks = args.tasks or sorted(p.stem for p in TASKS.glob("*.md"))
    with cf.ThreadPoolExecutor(args.workers) as pool:
        for f in cf.as_completed([pool.submit(task_group, t, args.reps, args.seed) for t in tasks]):
            f.result()
    return 0


if __name__ == "__main__":
    sys.exit(main())
