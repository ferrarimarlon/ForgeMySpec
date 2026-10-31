"""The conversation board: every request the user makes is a requirement, shown as status bars in the chat.

Requirements live in `forgemyspec-bundle/board/requirements.yaml` (written by Claude from the user's messages).
The figures come from the harness: the ledger in `.forgemyspec/state` and the session transcript. Read-only
except for `.forgemyspec/state/board-last.json`, which remembers the previous statuses to show what changed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import messages as M
from . import project

BOARD_FILE = Path("forgemyspec-bundle") / "board" / "requirements.yaml"
STATUSES = ("done", "doing", "open", "blocked")
WIDTH = 20
_HARNESS_COMMAND = re.compile(
    r"forgemyspec (gate|lint|package|kernel|lock|approve|unlock|init|suspend|request-approval|risk|board)|unittest|dafny")


def bar(part: float, total: float, width: int = WIDTH) -> str:
    full = round(width * part / total) if total else 0
    full = max(0, min(width, full))
    return "█" * full + "░" * (width - full)


def load(root: Path) -> List[Dict[str, Any]]:
    try:
        data = yaml.safe_load((root / BOARD_FILE).read_text(encoding="utf-8")) or []
    except OSError:
        return []
    return [r for r in data if isinstance(r, dict) and r.get("id")]


def activity(root: Path) -> Dict[str, int]:
    """Harness actions (harness commands run, guard checks) against model writes (Write/Edit), plus model tokens."""
    from .approvals import _transcripts

    runs = writes = tokens = 0
    seen = set()
    transcripts = _transcripts(root)
    if transcripts:
        for line in transcripts[0].read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message") or {}
            if message.get("id") not in seen:
                seen.add(message.get("id"))
                tokens += int((message.get("usage") or {}).get("output_tokens") or 0)
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                command = (block.get("input") or {}).get("command") or ""
                if block.get("name") == "Bash" and _HARNESS_COMMAND.search(command):
                    runs += 1
                elif block.get("name") in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
                    writes += 1
    checks = sum(1 for e in project.read_ledger(root) if e.get("event") == "pre-tool-use")
    return {"runs": runs, "checks": checks, "writes": writes, "tokens": tokens}


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


def progress(r: Dict[str, Any]) -> int:
    """Percent of a requirement's checkable steps that are done; a done requirement is 100."""
    if r.get("status") == "done":
        return 100
    steps = [x for x in r.get("steps") or [] if isinstance(x, dict)]
    return round(100 * sum(1 for x in steps if x.get("ok")) / len(steps)) if steps else 0


def _short(text: str, width: int = 40) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _tokens(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{round(n / 1000)}k"


def render(root: Path) -> str:
    reqs = load(root)
    act = activity(root)
    total = len(reqs)
    counts = {s: sum(1 for r in reqs if r.get("status", "open") == s) for s in STATUSES}
    harness = act["runs"] + act["checks"]
    decided = harness + act["writes"]
    lines = [M.BOARD_TITLE.format(n=total)]
    lines.append(M.BOARD_ROW.format(label=M.BOARD_DONE_LABEL, bar=bar(counts["done"], total),
                                    value=f"{counts['done']}/{total}"))
    for status in ("doing", "open", "blocked"):
        lines.append(M.BOARD_ROW.format(label=M.BOARD_STATUS[status], bar=bar(counts[status], total),
                                        value=str(counts[status])))
    lines.append("")
    hp = round(100 * harness / decided) if decided else 0
    lines.append(M.BOARD_ROW.format(label=M.BOARD_HARNESS, bar=bar(harness, decided),
                                    value=M.BOARD_HARNESS_VALUE.format(p=hp, runs=act["runs"], checks=act["checks"])))
    lines.append(M.BOARD_ROW.format(label=M.BOARD_MODEL, bar=bar(act["writes"], decided),
                                    value=M.BOARD_MODEL_VALUE.format(p=100 - hp if decided else 0, writes=act["writes"],
                                                                     tokens=_tokens(act["tokens"]))))
    active = sorted((r for r in reqs if r.get("status", "open") != "done"),
                    key=lambda r: (("doing", "blocked", "open").index(r.get("status", "open")), r["id"]))
    if active:
        lines.append("")
        for r in active:
            p = progress(r)
            lines.append(M.BOARD_ACTIVE.format(icon=M.BOARD_ICON[r.get("status", "open")], id=r["id"],
                                               bar=bar(p, 100, 10), p=p, title=_short(str(r.get("title", "")))))
    changed = _changed(root, reqs)
    by_id = {r["id"]: r for r in reqs}
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
    out = [M.BOARD_ITEM.format(icon=M.BOARD_ICON[r.get("status", "open")], id=r["id"], title=r.get("title", ""))]
    out.append(M.BOARD_PROGRESS.format(bar=bar(progress(r), 100, 10), p=progress(r)))
    for step in r.get("steps") or []:
        if isinstance(step, dict):
            out.append(M.BOARD_STEP.format(mark="✓" if step.get("ok") else "·", text=step.get("do", "")))
    for key in ("quote", "done", "evidence", "harness", "next"):
        if r.get(key):
            out.append(M.BOARD_FIELD.format(label=M.BOARD_FIELDS[key], text=r[key]))
    return "\n".join(out)
