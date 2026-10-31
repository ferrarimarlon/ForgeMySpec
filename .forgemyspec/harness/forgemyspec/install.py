"""`forgemyspec init`: installs ForgeMySpec in strict mode into a git repository.

Computes the desired state of each item, compares it with what exists and writes only what changes, with a
backup. A second run changes nothing. `--check` only compares and exits 1 when something differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import messages as M

PACKAGE = Path(__file__).resolve().parent
MARK_START = "<!-- forgemyspec:start -->"
MARK_END = "<!-- forgemyspec:end -->"
HOOK_MARK = "forgemyspec hook"
GITIGNORE_LINES = [".forgemyspec/state/", ".forgemyspec/backups/"]
HOOK_EVENTS = {
    "PreToolUse": ("pre-tool-use", "Edit|Write|MultiEdit|NotebookEdit|Bash", 15),
    "Stop": ("stop", None, 120),
    "SessionStart": ("session-start", None, 15),
    "UserPromptSubmit": ("user-prompt-submit", None, 15),
}

DEFAULT_CONFIG = """# ForgeMySpec configuration. Only the user edits this file (the guards protect it).
enforcement: strict
# Free text that is not code: allowed for editing and listed in the box as unverified text.
allow_paths:
  - "**/*.md"
  - "docs/**"
  - "LICENSE*"
# Folders left out of the analysis (besides .git, node_modules, .venv and similar).
ignore_dirs: [".git", "node_modules", ".venv", "venv", "__pycache__", ".forgemyspec", "generated", "_kernel", "build", "dist"]
"""

CLAUDE_BLOCK = """{start}
## ForgeMySpec (strict mode)

This repository uses ForgeMySpec. The guards are deterministic hooks: they deny edits outside the flow.

1. `/forgemyspec`: write the spec (with the `formal` section) and run the lint.
2. `/forgemyspec-formalize`: write the contract, tests and planted errors; the **user** approves by running `lock`.
3. `/forgemyspec-implement`: implement and run the gate until it passes.
4. `/forgemyspec-amend`: amendments always with the user's approval.

Harness commands (Claude may run `lint`, `package`, `gate`, `risk`, `lock --check` and `request-approval`;
`lock`, `approve`, `unlock` and `init` need the user's approval: the code from `request-approval`, typed by the
user in the chat, or the user running the command in their own terminal):

```bash
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec lint <spec.yaml> --formal
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec gate <bundle>
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec risk
```
{end}"""

PRE_COMMIT = """#!/bin/sh
# Installed by `forgemyspec init`: runs the gate on bundles with staged changes.
# A previous project pre-commit was kept as pre-commit.local and runs first.
if [ -x "$(dirname "$0")/pre-commit.local" ]; then
  "$(dirname "$0")/pre-commit.local" "$@" || exit $?
fi
PYTHONPATH=.forgemyspec/harness {python} -m forgemyspec hook pre-commit
"""

WORKFLOW = """name: ForgeMySpec gate

on:
  push:
  pull_request:

jobs:
  gate:
    name: ForgeMySpec gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: dafny-lang/setup-dafny-action@v1
        with:
          dafny-version: "4.11.0"
      - run: python -m pip install pyyaml
      - name: Gate on every approved bundle
        run: PYTHONPATH=.forgemyspec/harness python -m forgemyspec gate --all
"""


@dataclass
class Change:
    path: Path
    kind: str  # "created" | "updated"


class Plan:
    """Collects the comparison between desired and current state; applies it only when not --check."""

    def __init__(self, root: Path, check: bool):
        self.root = root
        self.check = check
        self.changes: List[Change] = []
        self.stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _backup(self, path: Path) -> None:
        target = self.root / ".forgemyspec" / "backups" / self.stamp / path.relative_to(self.root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())

    def file(self, path: Path, content: bytes, executable: bool = False, backup: bool = False) -> None:
        exists = path.exists()
        if exists and path.read_bytes() == content and (not executable or os.access(path, os.X_OK)):
            return
        self.changes.append(Change(path, "updated" if exists else "created"))
        if self.check:
            return
        if exists and backup:
            self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if executable:
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def mirror(self, target: Path, source: Path, ignore: Callable[[Path], bool] = lambda p: False) -> None:
        """Makes `target` identical to `source` (new, changed and removed files)."""
        desired: Dict[str, bytes] = {}
        for p in sorted(source.rglob("*")):
            if p.is_file() and not ignore(p) and "__pycache__" not in p.parts:
                desired[p.relative_to(source).as_posix()] = p.read_bytes()
        for rel, content in desired.items():
            self.file(target / rel, content)
        if target.exists():
            for p in sorted(target.rglob("*")):
                rel = p.relative_to(target).as_posix()
                if p.is_file() and "__pycache__" not in p.parts and rel not in desired:
                    self.changes.append(Change(p, "updated"))
                    if not self.check:
                        p.unlink()


def _git_root(target: Path) -> Optional[Path]:
    r = subprocess.run(["git", "-C", str(target), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else None


def _assets() -> Path:
    for candidate in (PACKAGE.parent.parent / "plugins" / "forgemyspec", PACKAGE.parent / "assets" / "forgemyspec"):
        if (candidate / "skills").is_dir():
            return candidate
    raise FileNotFoundError("ForgeMySpec skills not found (plugins/forgemyspec or assets/forgemyspec)")


def _hook_command(python: str, event: str) -> str:
    return f'PYTHONPATH="$CLAUDE_PROJECT_DIR/.forgemyspec/harness" {python} -m forgemyspec hook {event}'


def _settings(current: Dict, python: str) -> Dict:
    new = json.loads(json.dumps(current))
    if new.get("defaultAgent") == "forgemyspec-default":
        del new["defaultAgent"]
    new["agent"] = "forgemyspec-default"
    hooks = new.setdefault("hooks", {})
    for event, (name, matcher, timeout) in HOOK_EVENTS.items():
        entries = [
            e for e in hooks.get(event, [])
            if not any(HOOK_MARK in (h.get("command") or "") for h in e.get("hooks", []))
        ]
        hook = {"type": "command", "command": _hook_command(python, name), "timeout": timeout}
        if event == "PreToolUse":
            hook["onFailure"] = "block"  # strict mode: a guard that breaks blocks
        if event == "Stop":
            hook["statusMessage"] = "ForgeMySpec: building the risk box"
        entry = {"matcher": matcher, "hooks": [hook]} if matcher else {"hooks": [hook]}
        hooks[event] = entries + [entry]
    return new


def _claude_md(current: str) -> str:
    block = CLAUDE_BLOCK.format(start=MARK_START, end=MARK_END)
    if MARK_START in current and MARK_END in current:
        before = current.split(MARK_START, 1)[0]
        after = current.split(MARK_END, 1)[1]
        return before + block + after
    separator = "" if not current or current.endswith("\n\n") else ("\n" if current.endswith("\n") else "\n\n")
    return current + separator + block + "\n"


def _skill_or_agent(plan: Plan, target: Path, source: Path) -> None:
    if target.is_symlink() and target.resolve() == source.resolve():
        return  # the ForgeMySpec repository itself: the symlink already points at the source
    if source.is_dir():
        plan.mirror(target, source)
    else:
        plan.file(target, source.read_bytes())


def install(target: Path, check: bool = False, python: str = "python3") -> int:
    root = _git_root(target)
    if root is None:
        print(M.INIT_NOT_GIT.format(path=target), flush=True)
        return 1
    probe = subprocess.run([python, "-c", "import yaml"], capture_output=True)
    if probe.returncode != 0:
        print(M.INIT_NO_YAML.format(python=python), flush=True)
        return 1

    plan = Plan(root, check)
    assets = _assets()
    harness = root / ".forgemyspec" / "harness"

    # 1. copied harness and assets (what hooks, pre-commit and CI run)
    plan.mirror(harness / "forgemyspec", PACKAGE)
    plan.mirror(harness / "assets" / "forgemyspec", assets)

    # 2. configuration (never overwrites the user's)
    config = root / ".forgemyspec" / "config.yaml"
    if not config.exists():
        plan.file(config, DEFAULT_CONFIG.encode("utf-8"))

    # 3. skills and agent
    for skill in sorted((assets / "skills").iterdir()):
        if skill.is_dir():
            _skill_or_agent(plan, root / ".claude" / "skills" / skill.name, skill)
    for agent in sorted((assets / "agents").glob("*.md")):
        _skill_or_agent(plan, root / ".claude" / "agents" / agent.name, agent)

    # 4. merged settings.json
    settings = root / ".claude" / "settings.json"
    current = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
    plan.file(settings, (json.dumps(_settings(current, python), indent=2, ensure_ascii=False) + "\n").encode("utf-8"), backup=True)

    # 4b. remove earlier ForgeMySpec hook entries from settings.local.json, so the box does not show twice
    local_settings = root / ".claude" / "settings.local.json"
    if local_settings.exists():
        try:
            local_data = json.loads(local_settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            local_data = None
        if isinstance(local_data, dict) and isinstance(local_data.get("hooks"), dict):
            cleaned = json.loads(json.dumps(local_data))
            for event in list(cleaned["hooks"]):
                kept = [e for e in cleaned["hooks"][event]
                        if not any(HOOK_MARK in (h.get("command") or "") for h in e.get("hooks", []))]
                if kept:
                    cleaned["hooks"][event] = kept
                else:
                    del cleaned["hooks"][event]
            if not cleaned["hooks"]:
                del cleaned["hooks"]
            if cleaned != local_data:
                plan.file(local_settings, (json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), backup=True)

    # 5. CLAUDE.md with a marked block
    claude = root / "CLAUDE.md"
    plan.file(claude, _claude_md(claude.read_text(encoding="utf-8") if claude.exists() else "").encode("utf-8"), backup=True)

    # 6. .gitignore
    gitignore = root / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    missing = [line for line in GITIGNORE_LINES if line not in text.splitlines()]
    if missing:
        new = text + ("" if not text or text.endswith("\n") else "\n") + "\n# ForgeMySpec local state.\n" + "\n".join(missing) + "\n"
        plan.file(gitignore, new.encode("utf-8"), backup=True)

    # 7. pre-commit (keeping an earlier hook as pre-commit.local)
    hooks_dir = root / ".githooks"
    pre = hooks_dir / "pre-commit"
    local = hooks_dir / "pre-commit.local"
    previous = None
    if pre.exists() and HOOK_MARK not in pre.read_text(encoding="utf-8", errors="replace") and not local.exists():
        previous = pre.read_bytes()
    else:
        git_hook = root / ".git" / "hooks" / "pre-commit"
        if git_hook.exists() and not local.exists() and not pre.exists():
            previous = git_hook.read_bytes()
    if previous is not None:
        plan.file(local, previous, executable=True)
    plan.file(pre, PRE_COMMIT.format(python=python).encode("utf-8"), executable=True, backup=True)
    hooks_path = subprocess.run(["git", "-C", str(root), "config", "--get", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
    if hooks_path != ".githooks":
        plan.changes.append(Change(root / ".git" / "config", "updated"))
        if not check:
            subprocess.run(["git", "-C", str(root), "config", "core.hooksPath", ".githooks"], check=True)

    # 8. CI
    plan.file(root / ".github" / "workflows" / "forgemyspec.yml", WORKFLOW.encode("utf-8"))

    def rel(p: Path) -> str:
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            return str(p)

    if check:
        if not plan.changes:
            print(M.INIT_CHECK_OK)
            return 0
        print(M.INIT_CHECK_DIFFERS)
        for c in plan.changes:
            print(f"  {rel(c.path)}")
        return 1
    if not plan.changes:
        print(M.INIT_UP_TO_DATE)
        return 0
    for c in plan.changes:
        print((M.INIT_CREATED if c.kind == "created" else M.INIT_UPDATED).format(path=rel(c.path)))
    print()
    print(M.INIT_DONE)
    print(M.INIT_BRANCH_PROTECTION)
    return 0
