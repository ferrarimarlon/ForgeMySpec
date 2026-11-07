"""The conversation board: every request the user makes is a requirement, shown as status bars in the chat.

Requirements live in `forgemyspec-board.yaml` at the project root. Each step of a requirement is its contract; a
step may name a check (`test: <unittest id>` or `cmd: <shell command>`). Only `verify` marks a step verified: it
runs the check, and the result holds while the code is unchanged (a fingerprint of every project file except the
board). A step marked `ok: true` without a check is only claimed. Activity, tokens and context come from the
current Claude Code session transcript.

Usage (from the project root):
  python3 -m forgemyspec.board                 the board
  python3 -m forgemyspec.board R7              one requirement in full
  python3 -m forgemyspec.board start R7        mark the requirement being worked on
  python3 -m forgemyspec.board verify [R7]     run the checks
  python3 -m forgemyspec.board hook-stop       Claude Code Stop hook: a reply without the board goes back once
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

BOARD_FILE = Path("forgemyspec-board.yaml")
STATE_DIR = Path(".forgemyspec") / "state"
CHECKS_FILE = "board-checks.json"
STATUSES = ("done", "doing", "open", "blocked")
WIDTH = 20
COMMAND = "PYTHONPATH=src python3 -m forgemyspec.board"
# Harness work: the ForgeMySpec CLI, its linter and the test runners it relies on.
HARNESS = re.compile(r"\bforgemyspec\b|\bunittest\b|\bpytest\b")
WRITES = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

TITLE = "ForgeMySpec · {n} requirements"
ROW = "{label:<9} {bar} {value}"
ICON = {"done": "✅", "doing": "🔵", "open": "⚪", "blocked": "🔴"}
MARK = {"verified": "✔", "stale": "↻", "failed": "✗", "claimed": "?", "todo": "·"}
VERIFIED = "{p}%  ✔ verified by checks ({n}/{total} steps)"
CLAIMED = "{p}%  ? claimed, no check ({n})"
REST_ITEM = {"stale": "↻ {n} stale", "failed": "✗ {n} failed", "todo": "· {n} to do"}
ACTIVITY = "activity  {runs} harness runs · {writes} model writes · {tokens} output tokens"
MEMORY = "memory    context {context} tokens"
ACTIVE = "{icon} {id} {bar} {p:>3}%  {marks:<10} {effort}  {tokens:>4}  {title}"
EFFORT = "H{h:>3}% M{m:>3}%"
EFFORT_NONE = "H   –  M   – "
EFFORT_LINE = "  effort {effort} · {tokens} output tokens  (H = harness runs, M = model writes)"
CONTRACT = "  contract:  ✔ verified  ↻ stale  ✗ failed  ? claimed  · to do"
FIELDS = {"quote": "you said", "done": "done", "evidence": "evidence", "waiting": "waiting", "next": "next"}
STOP_MISSING = ("The reply has no requirements board. Run `{command}` and paste its output whole, in a code block, "
                "at the end of the reply.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def find_root(start: Optional[str] = None) -> Path:
    env = os.getenv("CLAUDE_PROJECT_DIR")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    base = Path(start or os.getcwd()).resolve()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(base), capture_output=True, text=True)
    return Path(top.stdout.strip()).resolve() if top.returncode == 0 and top.stdout.strip() else base


def state_dir(root: Path) -> Path:
    path = root / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _ledger(root: Path) -> List[Dict[str, Any]]:
    path = root / STATE_DIR / "ledger.jsonl"
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _append_ledger(root: Path, entry: Dict[str, Any]) -> None:
    with open(state_dir(root) / "ledger.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def bar(part: float, total: float, width: int = WIDTH) -> str:
    full = max(0, min(width, round(width * part / total) if total else 0))
    return "█" * full + "░" * (width - full)


def load(root: Path) -> List[Dict[str, Any]]:
    try:
        data = yaml.safe_load((root / BOARD_FILE).read_text(encoding="utf-8")) or []
    except OSError:
        return []
    return [r for r in data if isinstance(r, dict) and r.get("id")]


# ---------------------------------------------------------------------------
# Checks: the only way a step becomes verified
# ---------------------------------------------------------------------------


def fingerprint(root: Path) -> str:
    """Hash of every tracked and untracked project file except the board itself and the board state."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
                            capture_output=True, text=True).stdout.split("\n")
    files = sorted(f for f in listed if f and f != BOARD_FILE.as_posix() and not f.startswith(STATE_DIR.as_posix())
                   and (root / f).is_file())
    digest = hashlib.sha256()
    if files:
        blobs = subprocess.run(["git", "-C", str(root), "hash-object", "--stdin-paths"], input="\n".join(files),
                               capture_output=True, text=True).stdout.split()
        for name, blob in zip(files, blobs):
            digest.update(f"{name}\0{blob}\n".encode("utf-8"))
    return digest.hexdigest()


def _checks(root: Path) -> Dict[str, Dict[str, Any]]:
    data = _read_json(root / STATE_DIR / CHECKS_FILE)
    return data if isinstance(data, dict) else {}


def run_check(root: Path, check: str, timeout: int = 900) -> bool:
    kind, _, body = check.partition(":")
    body = body.strip()
    env = dict(os.environ)
    if kind == "test":
        env["PYTHONPATH"] = os.pathsep.join(str(root / p) for p in ("src", "tests"))
        argv = [sys.executable, "-m", "unittest", body]
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
    (state_dir(root) / CHECKS_FILE).write_text(json.dumps(results, indent=1), encoding="utf-8")
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


def progress(r: Dict[str, Any], results: Dict[str, Dict[str, Any]], fp: str) -> int:
    steps = [x for x in r.get("steps") or [] if isinstance(x, dict)]
    if not steps:
        return 100 if r.get("status") == "done" else 0
    states = [step_state(x, results, fp) for x in steps]
    return round(100 * sum(1 for s in states if s in ("verified", "stale", "claimed")) / len(states))


# ---------------------------------------------------------------------------
# Activity: the current session transcript
# ---------------------------------------------------------------------------


def start(root: Path, rid: str) -> None:
    """Marks the requirement now being worked on: actions from here on count toward it."""
    _append_ledger(root, {"event": "board-focus", "id": rid.upper(), "ts": _now()})


def transcript(root: Path) -> Optional[Path]:
    """The session the Stop hook last saw, else the newest transcript of this project folder."""
    saved = _read_json(root / STATE_DIR / "session.json") or {}
    path = Path(saved.get("transcript_path") or "")
    if saved.get("transcript_path") and path.exists():
        return path
    folder = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))
    found = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime) if folder.is_dir() else []
    return found[-1] if found else None


def activity(root: Path) -> Dict[str, Any]:
    """Harness runs against model writes, model output tokens, the last context size, and the same per requirement
    while it was in focus (`start R<n>`)."""
    focuses = sorted((str(e.get("ts", "")), e["id"]) for e in _ledger(root)
                     if e.get("event") == "board-focus" and e.get("id"))
    runs = writes = tokens = context = 0
    per: Dict[str, Dict[str, int]] = {}
    seen = set()
    path = transcript(root)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path else []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message") or {}
        stamp = str(entry.get("timestamp") or "")
        rid = next((i for ts, i in reversed(focuses) if ts <= stamp), None)
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
            kind = None
            if block.get("name") == "Bash" and HARNESS.search((block.get("input") or {}).get("command") or ""):
                runs += 1
                kind = "runs"
            elif block.get("name") in WRITES:
                writes += 1
                kind = "writes"
            if kind and bucket is not None:
                bucket[kind] += 1
    return {"runs": runs, "writes": writes, "tokens": tokens, "context": context, "per": per,
            "focus": focuses[-1][1] if focuses else None}


def effort(act: Dict[str, Any], rid: str) -> str:
    bucket = act["per"].get(rid)
    if not bucket or not (bucket["runs"] + bucket["writes"]):
        return EFFORT_NONE
    h = round(100 * bucket["runs"] / (bucket["runs"] + bucket["writes"]))
    return EFFORT.format(h=h, m=100 - h)


def _tokens(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{round(n / 1000)}k"


def _short(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _changed(root: Path, reqs: List[Dict[str, Any]]) -> List[str]:
    path = state_dir(root) / "board-last.json"
    before = _read_json(path) or {}
    now = {r["id"]: r.get("status", "open") for r in reqs}
    path.write_text(json.dumps(now), encoding="utf-8")
    return [i for i, s in now.items() if before.get(i) != s]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _marks(states: List[str]) -> str:
    return " ".join(f"{MARK[s]}{states.count(s)}" for s in MARK if states.count(s))


def render(root: Path) -> str:
    reqs = load(root)
    act = activity(root)
    results, fp = _checks(root), fingerprint(root)
    total = len(reqs)
    counts = {s: sum(1 for r in reqs if r.get("status", "open") == s) for s in STATUSES}
    lines = [TITLE.format(n=total), ROW.format(label="done", bar=bar(counts["done"], total),
                                               value=f"{counts['done']}/{total}")]
    for status in ("doing", "open", "blocked"):
        lines.append(ROW.format(label=status, bar=bar(counts[status], total), value=str(counts[status])))

    states_by_req = {r["id"]: [step_state(s, results, fp) for s in r.get("steps") or [] if isinstance(s, dict)]
                     for r in reqs}
    every = [s for states in states_by_req.values() for s in states]
    steps, verified, claimed = len(every), every.count("verified"), every.count("claimed")
    pct = lambda n: round(100 * n / steps) if steps else 0  # noqa: E731
    lines += ["", ROW.format(label="harness", bar=bar(verified, steps),
                             value=VERIFIED.format(p=pct(verified), n=verified, total=steps)),
              ROW.format(label="model", bar=bar(claimed, steps), value=CLAIMED.format(p=pct(claimed), n=claimed))]
    rest = {s: every.count(s) for s in ("stale", "failed", "todo") if every.count(s)}
    if rest:
        lines.append(" " * 10 + " · ".join(REST_ITEM[s].format(n=n) for s, n in rest.items()))
    lines.append(ACTIVITY.format(runs=act["runs"], writes=act["writes"], tokens=_tokens(act["tokens"])))
    if act["context"]:
        lines.append(MEMORY.format(context=_tokens(act["context"])))

    by_id = {r["id"]: r for r in reqs}
    focus = by_id.get(act["focus"]) if act["focus"] else None
    focus = focus if focus and focus.get("status") != "done" else None
    waiting = [r for r in reqs if r.get("waiting") and r.get("status") != "done"]
    if focus or waiting:
        lines.append("")
    if focus:
        lines.append(f"NOW       {focus['id']} {_short(str(focus.get('title', '')), 44)}")
    for r in waiting:
        lines.append(f"WAITING   {r['id']} {_short(str(r['waiting']), 44)}")

    active = sorted((r for r in reqs if r.get("status", "open") != "done"),
                    key=lambda r: (("doing", "blocked", "open").index(r.get("status", "open")), str(r["id"])))
    if active:
        lines.append("")
        for r in active:
            p = progress(r, results, fp)
            bucket = act["per"].get(r["id"]) or {}
            lines.append(ACTIVE.format(icon=ICON[r.get("status", "open")], id=r["id"], bar=bar(p, 100, 10), p=p,
                                       marks=_marks(states_by_req[r["id"]]), effort=effort(act, r["id"]),
                                       tokens=_tokens(bucket["tokens"]) if bucket.get("tokens") else "–",
                                       title=_short(str(r.get("title", "")), 28)))
    unverified = [r["id"] for r in reqs if r.get("status") == "done"
                  and not any(s == "verified" for s in states_by_req[r["id"]])]
    if unverified:
        lines += ["", "done without a check: " + ", ".join(str(i) for i in unverified)]
    changed = _changed(root, reqs)
    if changed:
        lines += ["", "changed:"] + [f"{ICON[by_id[i].get('status', 'open')]} {i} {by_id[i].get('title', '')}"
                                     for i in changed]
    return "\n".join(lines)


def detail(root: Path, rid: str) -> str:
    r = next((x for x in load(root) if str(x["id"]).lower() == rid.lower()), None)
    if r is None:
        return f"No requirement {rid} on the board."
    results, fp = _checks(root), fingerprint(root)
    act = activity(root)
    p = progress(r, results, fp)
    bucket = act["per"].get(r["id"]) or {}
    out = [f"{ICON[r.get('status', 'open')]} {r['id']} {r.get('title', '')}",
           f"  progress {bar(p, 100, 10)} {p}%",
           EFFORT_LINE.format(effort=effort(act, r["id"]), tokens=_tokens(bucket.get("tokens", 0)))]
    if r.get("steps"):
        out.append(CONTRACT)
    for step in r.get("steps") or []:
        if isinstance(step, dict):
            check = f"  [{step['check']}]" if step.get("check") else ""
            out.append(f"  {MARK[step_state(step, results, fp)]} {step.get('do', '')}{check}")
    for key, label in FIELDS.items():
        if r.get(key):
            out.append(f"  {label}: {r[key]}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Stop hook
# ---------------------------------------------------------------------------


def _last_reply(event: Dict[str, Any]) -> str:
    text = event.get("last_assistant_message")
    if isinstance(text, str):
        return text
    try:
        lines = Path(event.get("transcript_path") or "").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "assistant":
            texts = [b.get("text", "") for b in (entry.get("message") or {}).get("content") or []
                     if isinstance(b, dict) and b.get("type") == "text"]
            if texts:
                return "\n".join(texts)
    return ""


def hook_stop(event: Dict[str, Any]) -> Dict[str, Any]:
    """Remembers the session transcript; a reply without the board is sent back once to paste it."""
    root = find_root(event.get("cwd"))
    if event.get("transcript_path"):
        (state_dir(root) / "session.json").write_text(json.dumps({"transcript_path": event["transcript_path"]}))
    if (root / BOARD_FILE).exists() and not event.get("stop_hook_active") \
            and not re.search(r"ForgeMySpec · \d+ requirements", _last_reply(event)):
        return {"decision": "block", "reason": STOP_MISSING.format(command=COMMAND)}
    return {}


def main(argv: List[str]) -> int:
    if argv[:1] == ["hook-stop"]:
        try:
            event = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            event = {}
        print(json.dumps(hook_stop(event)))
        return 0
    root = find_root()
    if argv[:1] == ["verify"]:
        ran = verify(root, argv[1] if len(argv) > 1 else None)
        for rid, check, passed in ran:
            print(f"{'✔' if passed else '✗'} {rid}  {check}")
        print(f"{sum(1 for *_, ok in ran if ok)}/{len(ran)} checks passed")
        return 0 if all(ok for *_, ok in ran) else 1
    if argv[:1] == ["start"] and len(argv) == 2:
        start(root, argv[1])
        print(detail(root, argv[1]))
        return 0
    print(detail(root, argv[0]) if argv else render(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
