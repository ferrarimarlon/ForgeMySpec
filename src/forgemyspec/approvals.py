"""Approvals typed in the chat, turned into harness records.

Claude asks with `request-approval`: the harness binds a short code to the hash of exactly what is approved.
The user types the code in the chat. An approval counts only when the session transcript holds a message of
human origin, recorded after the request, that contains the code; the content is unchanged; and the approval
was not used yet. Whether it counts is decided by the trust kernel (TrustKernel.DecideApproval).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import project

ACTIONS = ("lock", "approve", "unlock", "init")
APPROVALS_FILE = "approvals.json"
SESSIONS_FILE = "sessions.json"


def _now() -> str:
    # Same shape as the transcript timestamps (milliseconds, Z), so plain string comparison orders them.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# What is being approved
# ---------------------------------------------------------------------------


def content_sha(root: Path, action: str, target: str) -> str:
    """Hash of exactly what the approval covers; any change makes an earlier approval stale."""
    from .bundle import BundleLayout
    from .contract_lock import compute_lock, compute_spec_lock
    from .spec_io import load_spec

    path = (root / target).resolve()
    if action == "init":
        from .install import PACKAGE

        digest = hashlib.sha256(str(path).encode("utf-8"))
        for p in sorted(PACKAGE.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                digest.update(p.relative_to(PACKAGE).as_posix().encode("utf-8") + b"\0" + p.read_bytes())
        return digest.hexdigest()
    layout = BundleLayout.at(path)
    if action == "unlock":
        locks = [p for p in (layout.lock, layout.root / "spec.lock") if p.exists()]
        return _sha(b"".join(p.read_bytes() for p in locks)) if locks else "no-lock"
    spec = load_spec(str(layout.spec))
    payload = compute_lock(layout, spec) if action == "lock" else compute_spec_lock(layout.root, spec)
    return _sha(json.dumps(payload, sort_keys=True).encode("utf-8"))


def _normalize(root: Path, target: str) -> str:
    """Project-relative path ("." for the root itself); a target outside the project keeps its absolute path."""
    path = (root / target).resolve()
    return project.rel(root.resolve(), path) or str(path)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def _read(root: Path, name: str) -> Dict[str, Any]:
    try:
        data = json.loads((project.state_dir(root) / name).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(root: Path, name: str, data: Dict[str, Any]) -> None:
    (project.state_dir(root) / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def remember_transcript(root: Path, session_id: Optional[str], transcript_path: Optional[str]) -> None:
    """Hooks call this so commands run later in the session know where the transcript is."""
    if not session_id or not transcript_path:
        return
    data = _read(root, SESSIONS_FILE)
    if (data.get(session_id) or {}).get("transcript_path") == transcript_path:
        return
    data[session_id] = {"transcript_path": transcript_path, "updated_at": _now()}
    try:
        _write(root, SESSIONS_FILE, data)
    except OSError:
        pass


def _transcripts(root: Path) -> List[Path]:
    known = [Path(v["transcript_path"]).expanduser() for v in _read(root, SESSIONS_FILE).values()
             if isinstance(v, dict) and v.get("transcript_path")]
    # Fallback: Claude Code keeps a project's transcripts under ~/.claude/projects/<path with / replaced by ->.
    folder = Path.home() / ".claude" / "projects" / str(root).replace("/", "-")
    if folder.is_dir():
        known += sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    unique: List[Path] = []
    for p in known:
        if p.exists() and p not in unique:
            unique.append(p)
    return unique


# ---------------------------------------------------------------------------
# Human-origin messages in a transcript
# ---------------------------------------------------------------------------


def human_messages(transcript: Path, since: str) -> List[Tuple[str, str]]:
    """(timestamp, text) of the messages the user typed after `since`.

    Typed messages are `user` entries with origin.kind == "human"; messages sent mid-turn are
    `queued_command` attachments with origin.kind == "human". Skill loads (isMeta), tool results and
    turns Claude Code starts on its own never count.
    """
    found = []
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return found
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        stamp = str(entry.get("timestamp") or "")
        if stamp < since:
            continue
        text = None
        if entry.get("type") == "user" and (entry.get("origin") or {}).get("kind") == "human" and not entry.get("isMeta"):
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list) and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                text = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        elif entry.get("type") == "attachment":
            attachment = entry.get("attachment") or {}
            if attachment.get("type") == "queued_command" and (attachment.get("origin") or {}).get("kind") == "human":
                prompt = attachment.get("prompt")
                text = prompt if isinstance(prompt, str) else None
        if text:
            found.append((stamp, text))
    return found


# ---------------------------------------------------------------------------
# Request, check, consume
# ---------------------------------------------------------------------------


@dataclass
class Verdict:
    approved: bool
    reason: Optional[str]
    code: Optional[str]
    how: str  # "terminal" | "chat"


def _code(nonce: str, records: List[Dict[str, str]]) -> str:
    """Six base32 characters derived from the nonce and exactly the items, so a code cannot be moved to other items."""
    items = [{k: r[k] for k in ("action", "target", "content_sha")} for r in records]
    digest = hashlib.sha256((nonce + json.dumps(items, sort_keys=True)).encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii")[:6]


def _intact(r: Dict[str, Any]) -> bool:
    return isinstance(r.get("nonce"), str) and r.get("code") == _code(r["nonce"], r.get("items") or [])


def request(root: Path, items: Iterable[Tuple[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    records = []
    for action, target in items:
        if action not in ACTIONS:
            raise ValueError(action)
        records.append({"action": action, "target": _normalize(root, target), "content_sha": content_sha(root, action, target)})
    nonce = secrets.token_hex(16)
    code = _code(nonce, records)
    data = _read(root, APPROVALS_FILE)
    data.setdefault("requests", []).append({"code": code, "nonce": nonce, "created_at": _now(), "items": [dict(r, used_at=None) for r in records]})
    _write(root, APPROVALS_FILE, data)
    return code, records


def _typed(root: Path, code: str, since: str) -> bool:
    return any(code in text.upper() for t in _transcripts(root) for _stamp, text in human_messages(t, since))


def check(root: Path, action: str, target: str, terminal: bool) -> Verdict:
    from . import kernel

    if terminal:
        approved, reason = kernel.decide_approval(True, False, False, False)
        return Verdict(approved, reason, None, "terminal")
    target = _normalize(root, target)
    current = content_sha(root, action, target)
    candidates = [(r, item) for r in _read(root, APPROVALS_FILE).get("requests", []) if _intact(r)
                  for item in r.get("items", []) if item.get("action") == action and item.get("target") == target]
    typed = [(r, item) for r, item in candidates if _typed(root, r["code"], r["created_at"])]
    # The most favourable request decides; the order also makes the refusal reason the precise one.
    preferences = (
        [c for c in typed if c[1]["content_sha"] == current and not c[1].get("used_at")],
        [c for c in typed if c[1]["content_sha"] == current],
        typed,
        candidates,
    )
    pick = next((group[-1] for group in preferences if group), None)
    request_, item = pick if pick else (None, None)
    approved, reason = kernel.decide_approval(
        terminal,
        pick is not None and pick in typed,
        item is not None and item["content_sha"] == current,
        item is not None and bool(item.get("used_at")),
    )
    return Verdict(approved, reason, request_["code"] if request_ else None, "terminal" if terminal else "chat")


def consume(root: Path, action: str, target: str, verdict: Verdict) -> None:
    if verdict.how == "terminal" or not verdict.code:
        return
    target = _normalize(root, target)
    data = _read(root, APPROVALS_FILE)
    for r in data.get("requests", []):
        if r.get("code") == verdict.code:
            for item in r.get("items", []):
                if item.get("action") == action and item.get("target") == target and not item.get("used_at"):
                    item["used_at"] = _now()
    _write(root, APPROVALS_FILE, data)


def pending_codes(root: Path) -> Dict[str, List[Dict[str, str]]]:
    return {r["code"]: [i for i in r.get("items", []) if not i.get("used_at")]
            for r in _read(root, APPROVALS_FILE).get("requests", []) if any(not i.get("used_at") for i in r.get("items", []))}


def is_terminal() -> bool:
    return os.isatty(0) and os.isatty(1)
