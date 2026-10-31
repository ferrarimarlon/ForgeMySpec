"""Risk box: what the gate guarantees about the project, requirement by requirement.

No color comes from the LLM. Everything comes from the proven kernel applied to the evidence the gate
recorded (.forgemyspec/state/gate) and to the files' current content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import messages as M
from . import project
from .contract_lock import approval_code, approved_at
from .dafny_lint import outline

WIDTH = 60
ORDER = {"leaking": 0, "fragile": 1, "proven": 2}


@dataclass
class Requirement:
    bundle: str
    phrase: str
    status: str
    reason: str


@dataclass
class Snapshot:
    requirements: List[Requirement]
    lines: Dict[str, int]
    text: int
    leaks: List[str]
    free_by_file: List[Tuple[str, int]]
    human: List[str]
    blocks: int = 0
    gates: int = 0
    tokens: Optional[Tuple[int, int, int]] = None
    change: Optional[float] = None
    strength: Dict[str, Dict[str, List[int]]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


def _obligation_reason(ev: Dict[str, Any]) -> str:
    reason = ev.get("reason")
    if reason == "failed":
        stage = (ev.get("fails") or [{}])[0].get("stage", "")
        return M.REASONS["failed"].format(stage=M.STAGES.get(stage, stage))
    if reason == "mutant":
        return M.REASONS["mutant"].format(n=len(ev.get("survivors") or []))
    return M.REASONS.get(reason, reason or "")


def _bundle_requirements(bundle: project.Bundle, status: project.GateStatus) -> List[Requirement]:
    from . import kernel

    metadata = bundle.spec.get("metadata") if isinstance(bundle.spec.get("metadata"), dict) else {}
    contract = metadata.get("scope_contract") if isinstance(metadata.get("scope_contract"), dict) else {}
    phrases = [p for p in contract.get("must_include") or [] if isinstance(p, str)]
    formal = bundle.spec.get("formal") if isinstance(bundle.spec.get("formal"), dict) else {}
    obligations = [o for o in formal.get("obligations") or [] if isinstance(o, dict)]

    gate = "none" if status.cached is None else ("current" if status.fresh else "stale")
    evidence = (status.cached or {}).get("evidence") or {}
    requirements = []
    for phrase in phrases:
        covering = [o["id"] for o in obligations if phrase in (o.get("must_include") or [])]
        evs = [evidence.get(i) or {"status": "leaking", "reason": "failed", "fails": [{"stage": "no-evidence"}]}
               for i in covering]
        # The color and the reason come from the proven kernel (TrustKernel.RequirementStatus).
        statuses = [e.get("status") if e.get("status") in ORDER else "leaking" for e in evs]
        color, reason, index = kernel.requirement_status(bundle.phase, gate, statuses)
        if reason == "obligation" and index is not None:
            text = _obligation_reason(evs[index])
        elif reason == "not-approved" and bundle.phase != "draft":
            text = M.REASONS["lock-invalid"] if bundle.phase == "lock-invalid" else M.REASONS["spec-invalid"]
        else:
            text = M.REASONS[reason]
        requirements.append(Requirement(bundle.name, phrase, color, text))
    return requirements


# ---------------------------------------------------------------------------
# Room to hallucinate
# ---------------------------------------------------------------------------


def _non_blank(text: str) -> List[int]:
    return [i for i, line in enumerate(text.splitlines(), start=1) if line.strip()]


def _impl_by_method(impl: str, band_by_method: Dict[str, str], default: str) -> Dict[str, int]:
    """Spreads impl.dfy lines over the bands, following the status of each method's obligations."""
    count = {"proven": 0, "examples": 0, "free": 0}
    band_by_line: Dict[int, str] = {}
    for member in outline(impl).members:
        if member.body_end <= 0:
            continue
        end = impl.count("\n", 0, member.body_end) + 1
        band = band_by_method.get(member.name, default)
        for line in range(member.line, end + 1):
            band_by_line[line] = band
    for line in _non_blank(impl):
        count[band_by_line.get(line, default)] += 1
    return count


def _band(status: str) -> str:
    return {"proven": "proven", "fragile": "examples"}.get(status, "free")


def classify_lines(
    root: Path, config: Dict[str, Any], bundles: List[project.Bundle], states: Dict[str, project.GateStatus]
) -> Tuple[Dict[str, int], int, List[Tuple[str, int]]]:
    from .gate import _obligations_by_method

    code = set(config["code_extensions"])
    text_ext = set(config["text_extensions"])
    lines = {"proven": 0, "examples": 0, "free": 0}
    text = 0
    free: Dict[str, int] = {}

    def healthy(b: project.Bundle) -> bool:
        s = states.get(b.name)
        return b.phase == "locked" and s is not None and s.fresh and s.passed

    for path in project.iter_project_files(root, config):
        r = project.rel(root, path)
        if r is None:
            continue
        suffix = path.suffix.lower()
        if suffix not in code:
            if suffix in text_ext or project.matches(r, config["allow_paths"]):
                try:
                    text += len(_non_blank(path.read_text(encoding="utf-8", errors="replace")))
                except OSError:
                    pass
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        owner = project.owning_bundle(bundles, r)
        inside = project.rel(owner.dir, path) if owner is not None else None
        if owner is not None and owner.formal and (path.name in {"contract.dfy", "tests.dfy"} or (inside or "").startswith("planted/")):
            continue  # specification approved by the user, not room for the LLM

        covering = [b for b in bundles if b.covers(r)]
        if not covering or not any(healthy(b) for b in covering):
            n = len(_non_blank(content))
            lines["free"] += n
            if n:
                free[r] = free.get(r, 0) + n
            continue

        bundle = next(b for b in covering if healthy(b))
        if bundle.formal and path.name == "impl.dfy" and owner is bundle:
            evidence = (states[bundle.name].cached or {}).get("evidence") or {}
            by_method = _obligations_by_method(bundle.layout.contract.read_text(encoding="utf-8"))
            band_by_method = {}
            for method, ids in by_method.items():
                worst = [s if s in ORDER else "leaking" for s in (evidence.get(i, {}).get("status") for i in ids)]
                band_by_method[method] = _band(min(worst, key=lambda s: ORDER.get(s, 0)) if worst else "leaking")
            for k, v in _impl_by_method(content, band_by_method, "proven").items():  # noqa: B007
                lines[k] += v
        else:
            lines["examples"] += len(_non_blank(content))
    return lines, text, sorted(free.items(), key=lambda kv: -kv[1])


# ---------------------------------------------------------------------------
# Turn tokens (read from the transcript; never estimated)
# ---------------------------------------------------------------------------


def turn_tokens(transcript_path: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not transcript_path:
        return None
    try:
        raw = Path(transcript_path).expanduser().read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    records = []
    for line in raw:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    start = 0
    for i, r in enumerate(records):
        if r.get("type") != "user" or r.get("isSidechain") or r.get("isMeta"):
            continue
        content = (r.get("message") or {}).get("content")
        if isinstance(content, str) or (
            isinstance(content, list)
            and any(isinstance(b, dict) and b.get("type") == "text" for b in content)
            and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
        ):
            start = i

    by_message: Dict[str, Dict[str, Any]] = {}
    for r in records[start:]:
        if r.get("type") != "assistant":
            continue
        message = r.get("message") or {}
        usage = message.get("usage")
        if isinstance(usage, dict):
            by_message[message.get("id") or str(len(by_message))] = usage
    if not by_message:
        return None
    total_in = sum(int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
                   + int(u.get("cache_read_input_tokens") or 0) for u in by_message.values())
    cached = sum(int(u.get("cache_read_input_tokens") or 0) for u in by_message.values())
    total_out = sum(int(u.get("output_tokens") or 0) for u in by_message.values())
    return total_in, cached, total_out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _human(bundle: project.Bundle) -> List[str]:
    lines = [(M.BOX_HUMAN_CONTRACT if bundle.formal else M.BOX_HUMAN_SPEC).format(bundle=bundle.name)]
    when = approved_at(bundle.lock_path) if bundle.phase == "locked" else ""
    if bundle.phase == "lock-invalid":
        lines.append("  " + M.BOX_HUMAN_LOCK_STALE)
    else:
        code = approval_code(bundle.lock_path) if when else ""
        if code:
            lines.append("  " + M.BOX_HUMAN_APPROVED_CHAT.format(when=_date(when), code=code))
        else:
            lines.append("  " + (M.BOX_HUMAN_APPROVED.format(when=_date(when)) if when else M.BOX_HUMAN_PENDING))
    context = bundle.spec.get("context") if isinstance(bundle.spec.get("context"), dict) else {}
    assumptions = [a for a in context.get("assumptions") or [] if isinstance(a, str)]
    if assumptions and when:
        lines.append(M.BOX_HUMAN_ASSUMPTIONS.format(n=len(assumptions)))
    return lines


def _date(iso: str) -> str:
    # 2026-10-31T14:02:11Z -> 10/31 14:02 UTC
    try:
        day, hour = iso.rstrip("Z").split("T")
        _year, month, dom = day.split("-")
        return f"{month}/{dom} {hour[:5]} UTC"
    except ValueError:
        return iso


def _shorten(path: str, limit: int = 34) -> str:
    """experiments/a/with-framework/16-secret-vault/vault.py -> experiments/…/with-framework/16-secret-vault/vault.py"""
    parts = path.split("/")
    if len(path) <= limit or len(parts) <= 4:
        return path
    return f"{parts[0]}/…/{'/'.join(parts[-3:])}"


def build(root: Path, transcript_path: Optional[str] = None, session: Optional[str] = None) -> Snapshot:
    config = project.load_config(root)
    bundles = project.discover_bundles(root, config)
    with_formal = [b for b in bundles if isinstance(b.spec.get("formal"), dict)]
    states = {b.name: project.gate_status(b, config) for b in bundles}

    requirements: List[Requirement] = []
    leaks: List[str] = []
    human: List[str] = []
    strength: Dict[str, Dict[str, List[int]]] = {}
    for bundle in with_formal:
        requirements += _bundle_requirements(bundle, states[bundle.name])
        human += _human(bundle)
        status = states[bundle.name]
        if not (status.fresh and status.cached):
            continue
        if status.cached.get("strength"):
            strength[bundle.name] = status.cached["strength"]
        for oid, ev in (status.cached.get("evidence") or {}).items():
            phrase = (ev.get("must_include") or [ev.get("statement") or oid])[0]
            for failure in ev.get("fails") or []:
                place = failure.get("place")
                if failure.get("stage") == "planted-errors":
                    leaks.append(M.LEAK_PLANTED.format(place=f"{bundle.name}/{place}"))
                elif place and failure.get("stage") == "verify":
                    leaks.append(M.LEAK_VERIFY.format(place=f"{bundle.name}/{place}", requirement=phrase))
                elif place:
                    leaks.append(M.LEAK_TEST.format(test=place))
            for alive in ev.get("survivors") or []:
                leaks.append(M.LEAK_MUTANT.format(place=f"{bundle.name}/{alive['place']}",
                                                  original=alive["original"], replacement=alive["replacement"]))

    lines, text, free = classify_lines(root, config, bundles, states)
    for path, n in free[:3]:
        leaks.append(M.LEAK_FREE.format(file=_shorten(path), n=n))
    if len(free) > 3:
        leaks.append(M.BOX_MORE.format(n=len(free) - 3).strip())

    unique: List[str] = []
    for leak in leaks:
        if leak not in unique:
            unique.append(leak)
    snapshot = Snapshot(requirements=requirements, lines=lines, text=text, leaks=unique,
                        free_by_file=free, human=human, strength=strength)
    snapshot.tokens = turn_tokens(transcript_path)

    total = sum(lines.values()) or 1
    proven = lines["proven"] / total
    previous = _read_previous(root)
    snapshot.change = None if previous is None else proven - previous
    _write_previous(root, proven)

    for entry in _turn_ledger(root, session):
        if entry.get("event") == "pre-tool-use" and entry.get("decision") == "deny":
            snapshot.blocks += 1
        if entry.get("event") == "gate":
            snapshot.gates += 1
    return snapshot


def _read_previous(root: Path) -> Optional[float]:
    path = root / project.STATE_DIR / "snapshot.json"
    try:
        return float(json.loads(path.read_text(encoding="utf-8"))["proven"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _write_previous(root: Path, proven: float) -> None:
    try:
        (project.state_dir(root) / "snapshot.json").write_text(json.dumps({"proven": proven}), encoding="utf-8")
    except OSError:
        pass


def _turn_ledger(root: Path, session: Optional[str]) -> List[Dict[str, Any]]:
    entries = project.read_ledger(root)
    starts = [i for i, e in enumerate(entries)
              if e.get("event") == "turn-start" and (session is None or e.get("session") == session)]
    return entries[starts[-1]:] if starts else []


# ---------------------------------------------------------------------------
# Rendering (at most 60 columns per line)
# ---------------------------------------------------------------------------


def _wrap(text: str, indent: str = "", continuation: Optional[str] = None) -> List[str]:
    following = indent + "  " if continuation is None else continuation
    return textwrap.wrap(text, width=WIDTH, initial_indent=indent, subsequent_indent=following,
                         break_on_hyphens=False) or [indent]


def _bar(fraction: float) -> str:
    full = round(fraction * 20)
    return "█" * full + "░" * (20 - full)


def _thousands(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def render(s: Snapshot) -> str:
    out: List[str] = [M.BOX_TITLE, "─" * 42, ""]

    if s.requirements:
        met = sum(1 for q in s.requirements if q.status != "leaking")
        out.append(M.BOX_REQUIREMENTS.format(met=met, total=len(s.requirements)))
        by_bundle: Dict[str, List[Requirement]] = {}
        for q in s.requirements:
            by_bundle.setdefault(q.bundle, []).append(q)
        for name, items in by_bundle.items():
            out += [""] + _wrap(f"▸ {name}", continuation="  ")
            strength = s.strength.get(name)
            if strength:
                killed, valid = strength.get("mutants") or [0, 0]
                rejected, total = strength.get("planted") or [0, 0]
                out += _wrap(M.BOX_STRENGTH.format(killed=killed, valid=valid, rejected=rejected, total=total), indent="  ")
            if len(items) > 1 and len({q.reason for q in items}) == 1 and items[0].status == "leaking":
                out += _wrap(f"{M.BOX_STATUS['leaking']} {len(items)} {M.BOX_SAME_REASON}")
                out += _wrap(items[0].reason, indent="   ")
                out += _wrap(", ".join(q.phrase for q in items), indent="   ")
                continue
            for q in sorted(items, key=lambda q: -ORDER[q.status]):
                out += _wrap(f"{M.BOX_STATUS[q.status]} {q.phrase}", continuation="   ")
                out += _wrap(q.reason, indent="   ")
    else:
        out.append(M.BOX_NO_REQUIREMENTS)

    out += ["", M.BOX_ROOM]
    total = sum(s.lines.values())
    for key in ("proven", "examples", "free"):
        n = s.lines[key]
        fraction = n / total if total else 0.0
        out.append(f"{M.BOX_BANDS[key]:<13} {_bar(fraction)} {fraction:>4.0%} {n:>5} {M.BOX_LINES}")
    pad = " " * 14
    if s.change is None:
        out.append(pad + M.BOX_CHANGE.format(change=M.BOX_FIRST))
    elif abs(s.change) < 0.005:
        out.append(pad + M.BOX_NO_CHANGE)
    else:
        sign = "+" if s.change > 0 else "−"
        out.append(pad + M.BOX_CHANGE.format(change=M.BOX_PROVEN_CHANGE.format(change=f"{sign}{abs(s.change):.0%}")))
    out.append(M.BOX_TEXT.format(n=s.text))

    out += ["", M.BOX_LEAKS]
    if s.leaks:
        for leak in s.leaks[:8]:
            out += _wrap(f"· {leak}")
        if len(s.leaks) > 8:
            out.append(M.BOX_MORE.format(n=len(s.leaks) - 8))
    else:
        out.append(f"· {M.BOX_NO_LEAKS}")

    if s.human:
        out += ["", M.BOX_HUMAN]
        for line in s.human:
            out += _wrap(line.strip(), indent="    ") if line.startswith(" ") else _wrap(f"· {line}")

    out += ["", M.BOX_PROMPT]
    out.append(f"· {M.BOX_PROMPT_BLOCKS.format(n=s.blocks)} · {M.BOX_PROMPT_GATES.format(n=s.gates)}")
    if s.tokens:
        total_in, cached, total_out = s.tokens
        out += _wrap(M.BOX_TOKENS.format(input=_thousands(total_in), cache=_thousands(cached), output=_thousands(total_out)))
    else:
        out.append(M.BOX_TOKENS_UNAVAILABLE)
    return "\n".join(out)
