"""Entry points for the Claude Code hooks: `python -m forgemyspec hook <event>`.

Each function reads the JSON Claude Code sends on stdin and prints its answer as JSON on stdout.
The decision to allow or deny an edit comes from the proven kernel (kernel.decide_edit); this module
only classifies paths, simulates edits and builds messages. Nothing here calls an LLM or the network.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Tuple

import yaml

from . import messages as M
from . import project

MAX_STOP_BLOCKS = 3
FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_input(stdin: TextIO) -> Dict[str, Any]:
    text = stdin.read()
    if not text.strip():
        return {}
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def harness_command(root: Path, action: str, target: str = "") -> str:
    """The command the user runs in their own terminal, with this installation's harness."""
    base = "PYTHONPATH=.forgemyspec/harness" if (root / ".forgemyspec" / "harness").is_dir() else "PYTHONPATH=src"
    return f"{base} python3 -m forgemyspec {action} {target}".strip()


# ---------------------------------------------------------------------------
# Path classification (Python glue; the decision belongs to the kernel)
# ---------------------------------------------------------------------------

CONTRACT_FILES = {"contract.dfy", "tests.dfy"}
IMPL_FILES = {"impl.dfy"}


def user_protected(path: Path) -> bool:
    """Session transcripts hold the user's typed approvals, and user settings hold the hooks: never Claude's to edit."""
    claude = (Path.home() / ".claude").resolve()
    try:
        inner = path.resolve().relative_to(claude).as_posix()
    except ValueError:
        return False
    return inner.startswith("projects/") or project.matches(inner, ["settings.json", "settings.local.json", "settings*.json"])


def categorize(
    root: Path, config: Dict[str, Any], bundles: List[project.Bundle], path: Path
) -> Tuple[str, Optional[project.Bundle], bool]:
    """Returns (kernel category, relevant bundle, whether a bundle covering the path is approved)."""
    if user_protected(path):
        return "Protected", None, False
    r = project.rel(root, path)
    if r is None:
        return "OutsideProject", None, False
    if project.is_protected(r):
        return "Protected", None, False

    owner = project.owning_bundle(bundles, r)
    if owner is not None:
        inner = project.rel(owner.dir, path) or ""
        top = inner.split("/", 1)[0]
        if inner == "spec.yaml":
            return "BundleSpec", owner, False
        if inner in CONTRACT_FILES or top == "planted":
            return "BundleContract", owner, False
        if inner in IMPL_FILES or top in {"shell", "tests_py"}:
            return "BundleImpl", owner, False
        if path.suffix.lower() in set(config["code_extensions"]):
            return "BundleImpl", owner, False
        return "BundleDoc", owner, False

    if path.name == "spec.yaml":
        return "BundleSpec", None, False  # new bundle: draft
    if project.matches(r, config["allow_paths"]):
        return "Allowed", None, False
    covering = [b for b in bundles if b.covers(r)]
    if covering:
        approved = any(b.phase == "locked" for b in covering)
        return "ScopeCovered", next((b for b in covering if b.phase == "locked"), covering[0]), approved
    return "NotCovered", None, False


def _new_content(tool: str, data: Dict[str, Any], current: str) -> Optional[str]:
    if tool == "Write":
        return data.get("content")
    if tool == "Edit":
        old, new = data.get("old_string", ""), data.get("new_string", "")
        return current.replace(old, new) if data.get("replace_all") else current.replace(old, new, 1)
    if tool == "MultiEdit":
        text = current
        for e in data.get("edits") or []:
            old, new = e.get("old_string", ""), e.get("new_string", "")
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
        return text
    return None


def _changes_formal(bundle: Optional[project.Bundle], path: Path, tool: str, data: Dict[str, Any]) -> bool:
    """Does the edit change the locked formal section or version? When it cannot tell, it assumes yes."""
    if bundle is None or not bundle.locked:
        return False
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        return True
    new = _new_content(tool, data, current)
    if new is None:
        return True
    try:
        parsed = yaml.safe_load(new)
    except yaml.YAMLError:
        return True
    if not isinstance(parsed, dict):
        return True
    return parsed.get("formal") != bundle.spec.get("formal") or str(parsed.get("version")) != str(bundle.spec.get("version"))


def _message(reason: str, root: Path, path: str, bundle: Optional[project.Bundle]) -> str:
    name = bundle.name if bundle else ""
    approve = harness_command(root, "lock" if (bundle and bundle.formal) else "approve", name)
    unlock = harness_command(root, "unlock", name)
    texts = {
        "RProtected": (M.GUARD_PROTECTED.format(path=path), None),
        "ROutsideSpec": (M.GUARD_OUTSIDE_SPEC.format(path=path), M.GUARD_OUTSIDE_SPEC_STEP),
        "RNotApproved": (M.GUARD_NOT_APPROVED.format(bundle=name, path=path), M.GUARD_NOT_APPROVED_STEP.format(command=approve)),
        "RContractLocked": (M.GUARD_CONTRACT_LOCKED.format(path=path), M.GUARD_CONTRACT_LOCKED_STEP.format(command=unlock)),
        "RFormalLocked": (M.GUARD_FORMAL_LOCKED.format(path=path), M.GUARD_CONTRACT_LOCKED_STEP.format(command=unlock)),
        "RSpecLocked": (M.GUARD_SPEC_LOCKED.format(path=path), M.GUARD_CONTRACT_LOCKED_STEP.format(command=unlock)),
        "RImplWithoutLock": (M.GUARD_IMPL_WITHOUT_LOCK.format(path=path, bundle=name), M.GUARD_IMPL_WITHOUT_LOCK_STEP.format(command=approve)),
        "RLockInvalid": (M.GUARD_LOCK_INVALID.format(bundle=name), M.GUARD_LOCK_INVALID_STEP.format(command=approve)),
        "RSpecInvalid": (M.GUARD_SPEC_INVALID.format(bundle=name, error=bundle.spec_error if bundle else ""), M.GUARD_SPEC_INVALID_STEP),
    }
    text, step = texts[reason]
    return text + (M.GUARD_NEXT.format(step=step) if step else "")


def decide_path(
    root: Path, config: Dict[str, Any], bundles: List[project.Bundle], path: Path,
    tool: str = "Write", data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """(allow, message). The decision comes from TrustKernel.DecideEdit."""
    from . import kernel

    category, bundle, covering_approved = categorize(root, config, bundles, path)
    if bundle is not None:
        phase, formal = bundle.phase, bundle.formal
    else:
        phase, formal = "draft", False
    changes = category == "BundleSpec" and _changes_formal(bundle, path, tool, data or {})
    allow, reason = kernel.decide_edit(category, formal, phase, changes, covering_approved)
    if allow:
        return True, ""
    return False, _message(reason, root, project.rel(root, path) or str(path), bundle)


# ---------------------------------------------------------------------------
# Bash guard
# ---------------------------------------------------------------------------

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")"}
_REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
_CODE_WRITES = re.compile(r"open\([^)]*['\"][wax]\+?b?['\"]|\.write_text\(|\.write_bytes\(|shutil\.(copy|move|rmtree)|os\.(remove|rename|replace|unlink)")
_LITERAL = re.compile(r"""['"]([^'"\s]+\.[A-Za-z0-9]+|[^'"\s]*/[^'"\s]+)['"]""")
_HUMAN_COMMANDS = {"lock", "unlock", "approve", "init"}


def _split_heredocs(command: str) -> Tuple[str, List[str]]:
    """Removes heredoc bodies from the command line and returns them separately."""
    lines, bodies, i = command.split("\n"), [], 0
    out: List[str] = []
    while i < len(lines):
        line = lines[i]
        out.append(line)
        delimiters = [m.group(2) for m in _HEREDOC.finditer(line)]
        i += 1
        for delimiter in delimiters:
            body = []
            while i < len(lines) and lines[i].strip() != delimiter:
                body.append(lines[i])
                i += 1
            i += 1
            bodies.append("\n".join(body))
    return "\n".join(out), bodies


def _tokens(command: str) -> List[str]:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def _simple_commands(tokens: List[str]) -> List[List[str]]:
    groups, current = [], []
    for t in tokens:
        if t in _SEPARATORS or (t and set(t) <= set(";&|()")):
            if current:
                groups.append(current)
            current = []
        else:
            current.append(t)
    if current:
        groups.append(current)
    return groups


def _write_targets(group: List[str]) -> List[str]:
    targets: List[str] = []
    i = 0
    while i < len(group):
        if group[i] in _REDIRECTS and i + 1 < len(group):
            target = group[i + 1]
            if not target.startswith("&") and target != "/dev/null":
                targets.append(target)
            i += 2
            continue
        i += 1
    words = [t for t in group if t not in _REDIRECTS | {"<"}]
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):  # skip env assignments (FOO=1 cmd)
        words = words[1:]
    if not words:
        return targets
    cmd, args = os.path.basename(words[0]), [a for a in words[1:] if not a.startswith("-")]
    if cmd == "tee":
        targets += args
    elif cmd in {"sed", "perl"} and any(a.startswith("-i") or a == "-pi" for a in words[1:]):
        targets += args[1:] if args else []
    elif cmd in {"cp", "mv", "install", "ln", "rsync"} and args:
        targets.append(args[-1])
    elif cmd in {"rm", "rmdir", "touch", "truncate", "chmod", "chown", "unlink"}:
        targets += args
    elif cmd == "dd":
        targets += [a[3:] for a in words[1:] if a.startswith("of=")]
    return targets


def _git_skips_hooks(group: List[str]) -> bool:
    if not group or os.path.basename(group[0]) != "git":
        return False
    if any("core.hookspath" in t.lower() for t in group):
        return True
    if "commit" in group:
        after = group[group.index("commit") + 1:]
        return any(t == "--no-verify" or re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", t) is not None for t in after)
    return False


def _human_command(group: List[str]) -> Optional[Tuple[str, str]]:
    """(action, target) of an approval command (`lock`, `unlock`, `approve`, `init`), or None."""
    if "forgemyspec" not in group:
        return None
    rest = group[group.index("forgemyspec") + 1:]
    words = [t for t in rest if not t.startswith("-")]
    action = words[0] if words else ""
    if action not in _HUMAN_COMMANDS or "--check" in rest:
        return None
    if action == "init":
        # --python takes a value; the target is the first other word.
        values = {rest[i + 1] for i, t in enumerate(rest[:-1]) if t == "--python"}
        words = [w for w in words if w not in values]
    return action, (words[1] if len(words) > 1 else ".")


def _human_decision(root: Path, cwd: Path, action: str, target: str) -> Tuple[bool, str]:
    from . import approvals

    path = Path(target).expanduser()
    path = (path if path.is_absolute() else cwd / path).resolve()
    command = f"forgemyspec {action} {target}"
    try:
        verdict = approvals.check(root, action, str(path), terminal=False)
    except Exception as exc:  # cannot compute what is approved: strict mode denies
        return False, M.GUARD_HUMAN_COMMAND.format(command=command, reason=M.APPROVAL_UNREADABLE.format(item=f"{action}:{target}", error=exc))
    if verdict.approved:
        return True, ""
    reason = M.APPROVAL_REFUSED[verdict.reason].format(action=action, target=target, code=verdict.code)
    step = M.GUARD_HUMAN_COMMAND_STEP.format(command=harness_command(root, "request-approval", f"{action}:{target}"))
    return False, M.GUARD_HUMAN_COMMAND.format(command=command, reason=reason) + M.GUARD_NEXT.format(step=step)


def decide_bash(root: Path, config: Dict[str, Any], bundles: List[project.Bundle], command: str, cwd: Path) -> Tuple[bool, str]:
    line, bodies = _split_heredocs(command)
    if re.search(r"\bwrite_(spec_)?lock\s*\(", command):
        step = M.GUARD_HUMAN_COMMAND_STEP.format(command=harness_command(root, "request-approval", "<action>:<target>"))
        return False, M.GUARD_HUMAN_COMMAND.format(command="write_lock(...)", reason="") + M.GUARD_NEXT.format(step=step)

    targets: List[str] = []
    for group in _simple_commands(_tokens(line)):
        human = _human_command(group)
        if human:
            allow, message = _human_decision(root, cwd, *human)
            if not allow:
                return False, message
        if _git_skips_hooks(group):
            return False, M.GUARD_NO_VERIFY + M.GUARD_NEXT.format(step=M.GUARD_NO_VERIFY_STEP)
        targets += _write_targets(group)

    scripts = bodies + [m.group(2) for m in re.finditer(r"-c\s+(['\"])(.*?)\1", line, re.S)]
    for script in scripts:
        if _CODE_WRITES.search(script):
            targets += [m.group(1) for m in _LITERAL.finditer(script)]

    for target in targets:
        path = Path(target).expanduser()
        path = (path if path.is_absolute() else cwd / path).resolve()
        allow, message = decide_path(root, config, bundles, path, "Write", {})
        if not allow:
            return False, M.GUARD_SHELL_WRITE.format(path=project.rel(root, path) or target, reason=message)
    return True, ""


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _deny(reason: str) -> Dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}


def _remember(root: Path, event: Dict[str, Any]) -> None:
    from . import approvals

    approvals.remember_transcript(root, event.get("session_id"), event.get("transcript_path"))


def pre_tool_use(event: Dict[str, Any]) -> Dict[str, Any]:
    root = project.find_root(event.get("cwd"))
    _remember(root, event)
    config = project.load_config(root)
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    if not isinstance(data, dict):
        return _deny(M.GUARD_UNDECIDABLE.format(cause="unreadable tool_input"))
    bundles = project.discover_bundles(root, config)

    if tool in FILE_TOOLS:
        target = data.get("file_path") or data.get("notebook_path")
        if not isinstance(target, str) or not target:
            return _deny(M.GUARD_UNDECIDABLE.format(cause="file tool without a path"))
        path = Path(target)
        path = (path if path.is_absolute() else Path(event.get("cwd") or root) / path).resolve()
        allow, message = decide_path(root, config, bundles, path, tool, data)
        record = project.rel(root, path) or target
    elif tool == "Bash":
        command = data.get("command")
        if not isinstance(command, str):
            return _deny(M.GUARD_UNDECIDABLE.format(cause="unreadable shell command"))
        allow, message = decide_bash(root, config, bundles, command, Path(event.get("cwd") or root))
        record = command[:200]
    else:
        return {}

    project.append_ledger(root, {
        "event": "pre-tool-use", "tool": tool, "target": record, "session": event.get("session_id"),
        "decision": "allow" if allow else "deny", "ts": _now(),
    })
    return {} if allow else _deny(message)


def _state_text(root: Path) -> str:
    config = project.load_config(root)
    bundles = [b for b in project.discover_bundles(root, config) if isinstance(b.spec.get("formal"), dict) or b.scope_paths]
    mode = config.get("enforcement", "strict")
    if not bundles:
        return M.STATE_NONE.format(mode=mode)
    lines = [M.STATE_TITLE.format(mode=mode)]
    for b in bundles:
        status = project.gate_status(b, config)
        if b.phase == "locked":
            ready = status.fresh and status.passed
            gate = "pass" if ready else ("stale" if status.cached and not status.fresh else ("fail" if status.cached else "none"))
            phase = f"{M.PHASES['locked']}, {M.GATE_STATE[gate]}"
            step = M.STEPS["locked-ok" if ready else "locked-pending"].format(command=harness_command(root, "gate", b.name))
        else:
            phase = M.PHASES.get(b.phase, b.phase)
            action = "lock" if b.formal else "approve"
            step = M.STEPS.get(b.phase, M.STEPS["draft"]).format(command=harness_command(root, action, b.name))
        lines.append(M.STATE_LINE.format(bundle=b.name, kind=M.BUNDLE_KIND[b.formal], phase=phase, step=step))
    lines.append(M.STATE_RULES)
    return "\n".join(lines)


def session_start(event: Dict[str, Any]) -> Dict[str, Any]:
    root = project.find_root(event.get("cwd"))
    _remember(root, event)
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": _state_text(root)}}


def user_prompt_submit(event: Dict[str, Any]) -> Dict[str, Any]:
    root = project.find_root(event.get("cwd"))
    _remember(root, event)
    project.append_ledger(root, {"event": "turn-start", "session": event.get("session_id"), "ts": _now()})
    _write_blocks(root, event.get("session_id"), 0)
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": _state_text(root)}}


def _blocks_file(root: Path) -> Path:
    return project.state_dir(root) / "stop-blocks.json"


def _read_blocks(root: Path, session: Optional[str]) -> int:
    try:
        return int(json.loads(_blocks_file(root).read_text(encoding="utf-8")).get(session or "", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _write_blocks(root: Path, session: Optional[str], n: int) -> None:
    try:
        data = json.loads(_blocks_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    data[session or ""] = n
    try:
        _blocks_file(root).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def pending_gates(root: Path) -> List[Tuple[project.Bundle, str]]:
    """Approved bundles without a PASS gate for their current content, with the reason."""
    config = project.load_config(root)
    pending = []
    for b in project.discover_bundles(root, config):
        if b.phase != "locked" or not (isinstance(b.spec.get("formal"), dict) or b.scope_paths):
            continue
        status = project.gate_status(b, config)
        if status.cached is None:
            pending.append((b, M.STOP_REASON_NO_GATE))
        elif not status.fresh:
            pending.append((b, M.STOP_REASON_STALE))
        elif not status.passed:
            stages = ", ".join(M.STAGES.get(e, e) for e in status.failed_stages)
            pending.append((b, M.STOP_REASON_FAILED.format(stages=stages)))
    return pending


def stop(event: Dict[str, Any]) -> Dict[str, Any]:
    from . import risk

    root = project.find_root(event.get("cwd"))
    session = event.get("session_id")
    pending = pending_gates(root)
    blocks = _read_blocks(root, session)
    if pending and blocks < MAX_STOP_BLOCKS:
        _write_blocks(root, session, blocks + 1)
        reasons = "\n".join(
            M.STOP_BLOCK.format(bundle=b.name, reason=r, command=harness_command(root, "gate", b.name)) for b, r in pending
        )
        return {"decision": "block", "reason": reasons}
    _write_blocks(root, session, 0)
    try:
        box = risk.render(risk.build(root, event.get("transcript_path"), session))
    except Exception as exc:  # the box must never disappear silently
        box = M.STOP_BOX_ERROR.format(error=f"{type(exc).__name__}: {exc}")
    if pending:
        box = M.STOP_RELEASED_UNVERIFIED.format(bundles=", ".join(b.name for b, _ in pending)) + "\n\n" + box
    return {"systemMessage": box}


def pre_commit() -> int:
    """Called by .githooks/pre-commit (not by Claude Code): runs the gate on bundles with staged changes."""
    import subprocess

    from .gate import run_gate

    root = project.find_root()
    config = project.load_config(root)
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(root), capture_output=True, text=True).stdout.split()
    bundles = [b for b in project.discover_bundles(root, config) if b.phase != "draft" or b.locked]
    touched = [b for b in bundles if any(b.covers(f) for f in staged)]
    failed = [b.name for b in touched if not run_gate(str(b.dir)).passed]
    if failed:
        print(M.PRE_COMMIT_FAILED.format(bundles=", ".join(failed)), file=sys.stderr)
        return 1
    if touched:
        print(M.PRE_COMMIT_OK.format(n=len(touched)), file=sys.stderr)
    return 0


EVENTS = {
    "pre-tool-use": pre_tool_use,
    "stop": stop,
    "session-start": session_start,
    "user-prompt-submit": user_prompt_submit,
}


def main(name: str, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    if name == "pre-commit":
        return pre_commit()
    handler = EVENTS.get(name)
    if handler is None:
        print(M.GUARD_UNDECIDABLE.format(cause=f"unknown event: {name}"), file=sys.stderr)
        return 2
    try:
        answer = handler(_read_input(stdin))
    except Exception as exc:  # strict mode: when in doubt, block (exit 2) and say why
        print(M.GUARD_UNDECIDABLE.format(cause=f"{type(exc).__name__}: {exc}"), file=sys.stderr)
        return 2
    if answer:
        stdout.write(json.dumps(answer, ensure_ascii=False))
    return 0
