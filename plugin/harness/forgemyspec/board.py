"""The conversation board: every request the user makes is a requirement, shown as status bars in the chat.

Requirements live in `forgemyspec-bundle/board/requirements.yaml` in this repository, or `forgemyspec-board.yaml`
in a project. Each step of a requirement is its contract; a step may name a check (`test: <unittest id>` or
`cmd: <shell command>`). Only `board verify` marks a step verified: it runs the check, and the result holds while
the code is unchanged (a fingerprint of every project file except the board). A step marked `ok: true` without a
check is only claimed. Activity, tokens and memory come from the session transcript and the harness ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from . import messages as M
from . import project

BOARD_FILE = Path("forgemyspec-bundle") / "board" / "requirements.yaml"  # this repository
PROJECT_BOARD_FILE = Path("forgemyspec-board.yaml")  # any project with ForgeMySpec installed
CHECKS_FILE = "board-checks.json"
STATUSES = ("done", "doing", "open", "blocked")
WIDTH = 20
_HARNESS_COMMAND = re.compile(
    r"forgemyspec (gate|lint|package|kernel|lock|approve|unlock|init|suspend|request-approval|risk|board)|unittest|dafny")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def bar(part: float, total: float, width: int = WIDTH) -> str:
    full = round(width * part / total) if total else 0
    full = max(0, min(width, full))
    return "█" * full + "░" * (width - full)


def board_file(root: Path) -> Path:
    return root / BOARD_FILE if (root / BOARD_FILE).exists() else root / PROJECT_BOARD_FILE


def load(root: Path) -> List[Dict[str, Any]]:
    try:
        data = yaml.safe_load(board_file(root).read_text(encoding="utf-8")) or []
    except OSError:
        return []
    return [r for r in data if isinstance(r, dict) and r.get("id")]


# ---------------------------------------------------------------------------
# Checks: the only way a step becomes verified
# ---------------------------------------------------------------------------


def fingerprint(root: Path) -> str:
    """Hash of every tracked and untracked project file except the board itself and harness state."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
                            capture_output=True, text=True).stdout.split("\n")
    skip = {BOARD_FILE.as_posix(), PROJECT_BOARD_FILE.as_posix()}
    files = sorted(f for f in listed if f and f not in skip and not f.startswith(".forgemyspec/state/")
                   and (root / f).is_file())
    digest = hashlib.sha256()
    if files:
        blobs = subprocess.run(["git", "-C", str(root), "hash-object", "--stdin-paths"], input="\n".join(files),
                               capture_output=True, text=True).stdout.split()
        for name, blob in zip(files, blobs):
            digest.update(f"{name}\0{blob}\n".encode("utf-8"))
    return digest.hexdigest()


def _checks(root: Path) -> Dict[str, Dict[str, Any]]:
    try:
        data = json.loads((project.state_dir(root) / CHECKS_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def run_check(root: Path, check: str, timeout: int = 900) -> bool:
    kind, _, body = check.partition(":")
    body = body.strip()
    env = dict(os.environ)
    if kind == "test":
        paths = project.load_config(root).get("board_pythonpath") or ["src", "tests"]
        env["PYTHONPATH"] = os.pathsep.join(str(root / p) for p in paths)
        argv = ["python3", "-m", "unittest", body]
    elif kind == "cmd":
        argv = ["/bin/sh", "-c", body]
    else:
        return False
    try:
        return subprocess.run(argv, cwd=str(root), env=env, capture_output=True, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def verify(root: Path, rid: Optional[str] = None) -> List[Tuple[str, str, bool]]:
    """Runs the checks of every step (or of one requirement) and records each result with the code fingerprint."""
    fp = fingerprint(root)
    results = _checks(root)
    ran: List[Tuple[str, str, bool]] = []
    done: Dict[str, bool] = {}
    for r in load(root):
        if rid and str(r["id"]).lower() != rid.lower():
            continue
        for step in r.get("steps") or []:
            check = step.get("check") if isinstance(step, dict) else None
            if not check:
                continue
            if check not in done:
                started = time.time()
                done[check] = run_check(root, check)
                results[check] = {"passed": done[check], "fingerprint": fp, "ran_at": _now(),
                                  "seconds": round(time.time() - started, 1)}
            ran.append((r["id"], check, done[check]))
    (project.state_dir(root) / CHECKS_FILE).write_text(json.dumps(results, indent=1), encoding="utf-8")
    project.append_ledger(root, {"event": "board-verify", "id": rid, "checks": len(done), "ts": _now()})
    return ran


def step_state(step: Dict[str, Any], results: Dict[str, Dict[str, Any]], fp: str) -> str:
    """verified | stale | failed | claimed | todo"""
    check = step.get("check")
    result = results.get(check) if check else None
    if result:
        if not result.get("passed"):
            return "failed"
        return "verified" if result.get("fingerprint") == fp else "stale"
    return "claimed" if step.get("ok") else "todo"


def progress(r: Dict[str, Any], results: Optional[Dict[str, Dict[str, Any]]] = None, fp: str = "") -> int:
    """Percent of a requirement's steps that are done (verified, stale or claimed); without steps, done is 100."""
    steps = [x for x in r.get("steps") or [] if isinstance(x, dict)]
    if not steps:
        return 100 if r.get("status") == "done" else 0
    states = [step_state(x, results or {}, fp) for x in steps]
    return round(100 * sum(1 for s in states if s in ("verified", "stale", "claimed")) / len(states))


# ---------------------------------------------------------------------------
# Activity: the transcript and the ledger
# ---------------------------------------------------------------------------


def start(root: Path, rid: str) -> None:
    """Marks the requirement now being worked on: actions from here on count toward it."""
    project.append_ledger(root, {"event": "board-focus", "id": rid.upper(), "ts": _now()})


def _focus_at(focuses: List[tuple], stamp: str) -> Optional[str]:
    current = None
    for ts, rid in focuses:
        if ts <= stamp:
            current = rid
        else:
            break
    return current


def activity(root: Path) -> Dict[str, Any]:
    """Harness runs and guard checks against model writes, model output tokens, the last context size, and `per`:
    runs, writes and tokens of each requirement while it was in focus (`board start R<n>`). Read from the
    current session: the most recently written transcript."""
    from .approvals import _transcripts

    runs = writes = tokens = context = 0
    per: Dict[str, Dict[str, int]] = {}
    ledger = project.read_ledger(root)
    focuses = sorted((str(e.get("ts", "")), e["id"]) for e in ledger if e.get("event") == "board-focus" and e.get("id"))
    seen = set()
    transcripts = _transcripts(root)
    if transcripts:
        current = max(transcripts, key=lambda p: p.stat().st_mtime)
        for line in current.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message") or {}
            rid = _focus_at(focuses, str(entry.get("timestamp") or ""))
            bucket = per.setdefault(rid, {"runs": 0, "writes": 0, "tokens": 0}) if rid else None
            usage = message.get("usage") or {}
            if message.get("id") not in seen:
                seen.add(message.get("id"))
                out = int(usage.get("output_tokens") or 0)
                tokens += out
                if bucket is not None:
                    bucket["tokens"] += out
                size = sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens",
                                                            "cache_creation_input_tokens"))
                context = size or context
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                command = (block.get("input") or {}).get("command") or ""
                kind = None
                if block.get("name") == "Bash" and _HARNESS_COMMAND.search(command):
                    runs += 1
                    kind = "runs"
                elif block.get("name") in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
                    writes += 1
                    kind = "writes"
                if kind and bucket is not None:
                    bucket[kind] += 1
    checks = sum(1 for e in ledger if e.get("event") == "pre-tool-use")
    return {"runs": runs, "checks": checks, "writes": writes, "tokens": tokens, "context": context, "per": per,
            "focus": focuses[-1][1] if focuses else None}


def effort(act: Dict[str, Any], rid: str) -> str:
    bucket = act.get("per", {}).get(rid)
    if not bucket or not (bucket["runs"] + bucket["writes"]):
        return M.BOARD_EFFORT_NONE
    h = round(100 * bucket["runs"] / (bucket["runs"] + bucket["writes"]))
    return M.BOARD_EFFORT.format(h=h, m=100 - h)


def _tokens(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{round(n / 1000)}k"


def _short(text: str, width: int = 40) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _changed(root: Path, reqs: List[Dict[str, Any]]) -> List[str]:
    state = project.state_dir(root) / "board-last.json"
    try:
        before = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        before = {}
    now = {r["id"]: r.get("status", "open") for r in reqs}
    try:
        state.write_text(json.dumps(now), encoding="utf-8")
    except OSError:
        pass
    return [i for i, s in now.items() if before.get(i) != s]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _marks(states: List[str]) -> str:
    return " ".join(f"{M.BOARD_MARK[s]}{states.count(s)}" for s in ("verified", "stale", "failed", "claimed", "todo")
                    if states.count(s))


def render(root: Path) -> str:
    reqs = load(root)
    act = activity(root)
    results, fp = _checks(root), fingerprint(root)
    total = len(reqs)
    counts = {s: sum(1 for r in reqs if r.get("status", "open") == s) for s in STATUSES}
    lines = [M.BOARD_TITLE.format(n=total)]
    lines.append(M.BOARD_ROW.format(label=M.BOARD_DONE_LABEL, bar=bar(counts["done"], total),
                                    value=f"{counts['done']}/{total}"))
    for status in ("doing", "open", "blocked"):
        lines.append(M.BOARD_ROW.format(label=M.BOARD_STATUS[status], bar=bar(counts[status], total),
                                        value=str(counts[status])))

    # Evidence over every step: verified by a harness check against only claimed by the model.
    states_by_req = {r["id"]: [step_state(s, results, fp) for s in r.get("steps") or [] if isinstance(s, dict)]
                     for r in reqs}
    every = [s for states in states_by_req.values() for s in states]
    steps = len(every)
    verified, claimed = every.count("verified"), every.count("claimed")
    lines.append("")
    lines.append(M.BOARD_ROW.format(label=M.BOARD_HARNESS, bar=bar(verified, steps),
                                    value=M.BOARD_VERIFIED.format(p=round(100 * verified / steps) if steps else 0,
                                                                  n=verified, total=steps)))
    lines.append(M.BOARD_ROW.format(label=M.BOARD_MODEL, bar=bar(claimed, steps),
                                    value=M.BOARD_CLAIMED.format(p=round(100 * claimed / steps) if steps else 0,
                                                                 n=claimed)))
    rest = {s: every.count(s) for s in ("stale", "failed", "todo") if every.count(s)}
    if rest:
        lines.append(M.BOARD_REST.format(text=" · ".join(M.BOARD_REST_ITEM[s].format(n=n) for s, n in rest.items())))
    lines.append(M.BOARD_ACTIVITY.format(runs=act["runs"], checks=act["checks"], writes=act["writes"],
                                         tokens=_tokens(act["tokens"])))
    if act["context"]:
        lines.append(M.BOARD_MEMORY.format(context=_tokens(act["context"])))

    by_id = {r["id"]: r for r in reqs}
    focus = by_id.get(act["focus"]) if act["focus"] else None
    focus = focus if focus and focus.get("status") != "done" else None
    waiting = [r for r in reqs if r.get("waiting") and r.get("status") != "done"]
    if focus or waiting:
        lines.append("")
    if focus:
        lines.append(M.BOARD_NOW.format(id=focus["id"], title=_short(str(focus.get("title", "")), 44)))
    for r in waiting:
        lines.append(M.BOARD_WAITING.format(id=r["id"], text=_short(str(r["waiting"]), 44)))

    active = sorted((r for r in reqs if r.get("status", "open") != "done"),
                    key=lambda r: (("doing", "blocked", "open").index(r.get("status", "open")), r["id"]))
    if active:
        lines.append("")
        for r in active:
            p = progress(r, results, fp)
            bucket = act["per"].get(r["id"]) or {}
            lines.append(M.BOARD_ACTIVE.format(icon=M.BOARD_ICON[r.get("status", "open")], id=r["id"],
                                               bar=bar(p, 100, 10), p=p, marks=_marks(states_by_req[r["id"]]),
                                               effort=effort(act, r["id"]),
                                               tokens=_tokens(bucket["tokens"]) if bucket.get("tokens") else "–",
                                               title=_short(str(r.get("title", "")), 28)))
    unverified = [r["id"] for r in reqs if r.get("status") == "done"
                  and not any(s == "verified" for s in states_by_req[r["id"]])]
    if unverified:
        lines.append("")
        lines.append(M.BOARD_UNVERIFIED.format(ids=", ".join(unverified)))

    changed = _changed(root, reqs)
    if changed:
        lines.append("")
        lines.append(M.BOARD_CHANGED)
        for i in changed:
            r = by_id[i]
            lines.append(M.BOARD_ITEM.format(icon=M.BOARD_ICON[r.get("status", "open")], id=i, title=r.get("title", "")))
    return "\n".join(lines)


def detail(root: Path, rid: str) -> str:
    r = next((x for x in load(root) if str(x["id"]).lower() == rid.lower()), None)
    if r is None:
        return M.BOARD_UNKNOWN.format(id=rid)
    results, fp = _checks(root), fingerprint(root)
    act = activity(root)
    out = [M.BOARD_ITEM.format(icon=M.BOARD_ICON[r.get("status", "open")], id=r["id"], title=r.get("title", ""))]
    p = progress(r, results, fp)
    out.append(M.BOARD_PROGRESS.format(bar=bar(p, 100, 10), p=p))
    bucket = act["per"].get(r["id"]) or {}
    out.append(M.BOARD_EFFORT_LINE.format(effort=effort(act, r["id"]), tokens=_tokens(bucket.get("tokens", 0))))
    if r.get("steps"):
        out.append(M.BOARD_CONTRACT)
    for step in r.get("steps") or []:
        if isinstance(step, dict):
            state = step_state(step, results, fp)
            check = f"  [{step['check']}]" if step.get("check") else ""
            out.append(M.BOARD_STEP.format(mark=M.BOARD_MARK[state], text=step.get("do", "")) + check)
    for key in ("quote", "done", "evidence", "harness", "waiting", "next"):
        if r.get(key):
            out.append(M.BOARD_FIELD.format(label=M.BOARD_FIELDS[key], text=r[key]))
    return "\n".join(out)
