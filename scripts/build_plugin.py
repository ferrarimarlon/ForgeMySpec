"""Exports ForgeMySpec as a Claude Code plugin into its own repository (default: plugin/ in this repository).

The plugin carries the deterministic harness, the skills, the agent and the hooks (file and shell guards, state
summary). It is the place where the gates run on other projects; this repository stays the source.

Usage: python3 scripts/build_plugin.py [target-dir]
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "forgemyspec"
ASSETS = ROOT / "plugins" / "forgemyspec"
VERSION = "0.6.0"

HOOK = 'FORGEMYSPEC_HARNESS="${CLAUDE_PLUGIN_ROOT}/harness" PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/harness" python3 -m forgemyspec hook '
HOOKS = {
    "hooks": {
        "PreToolUse": [{"matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
                        "hooks": [{"type": "command", "command": HOOK + "pre-tool-use", "timeout": 15}]}],
        "SessionStart": [{"hooks": [{"type": "command", "command": HOOK + "session-start", "timeout": 15}]}],
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": HOOK + "user-prompt-submit", "timeout": 15}]}],
        "Stop": [{"hooks": [{"type": "command", "command": HOOK + "stop", "timeout": 30}]}],
    }
}

README = """# ForgeMySpec plugin

Spec-first development inside Claude Code: Claude writes the spec (and, for critical logic, a Dafny contract),
you approve it in the chat with a short code, and deterministic gates check the work. No external LLM calls.

## Install

```
/plugin marketplace add {path}
/plugin install forgemyspec@forgemyspec
```

Requirements: Python 3.9+ with PyYAML; Dafny 4.x only for formal (Dafny) bundles.

## What it does

- `/forgemyspec` writes a spec; spec-only by default, Dafny only for critical logic.
- Guards: edits need an approved spec that covers the path; locks, contracts and harness state are protected.
- Approval in the chat: `request-approval` prints a code bound to the content hash; you type it.
- `forgemyspec board`: every request as a requirement, with status bars and the harness vs model share.
- `forgemyspec gate <bundle>` (and `--fast` in the session): lint, tests, Dafny verification, mutation, planted errors.

Harness commands: `PYTHONPATH="<plugin>/harness" python3 -m forgemyspec <command>`.

Built from the ForgeMySpec repository with `scripts/build_plugin.py` (version {version}); do not edit by hand.
"""

SMOKE_TEST = '''"""Smoke test of the exported plugin: manifest, hooks and a guard decision."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_manifest_and_hooks(self) -> None:
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "forgemyspec")
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
        self.assertEqual(set(hooks), {"PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"})

    def test_guard_denies_a_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            event = {"tool_name": "Write", "cwd": tmp,
                     "tool_input": {"file_path": str(Path(tmp) / "b" / "contract.lock"), "content": "x"}}
            out = subprocess.run([sys.executable, "-m", "forgemyspec", "hook", "pre-tool-use"],
                                 input=json.dumps(event), capture_output=True, text=True,
                                 env={"PYTHONPATH": str(PLUGIN / "harness"), "PATH": "/usr/bin:/bin",
                                      "CLAUDE_PROJECT_DIR": tmp})
        self.assertEqual(json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
'''


def build(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in ("harness", "skills", "agents", "hooks", ".claude-plugin", "tests"):
        if (target / name).exists():
            shutil.rmtree(target / name)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(SOURCE, target / "harness" / "forgemyspec", ignore=ignore)
    shutil.copytree(ASSETS / "skills", target / "skills", ignore=ignore, symlinks=False)
    shutil.copytree(ASSETS / "agents", target / "agents", ignore=ignore, symlinks=False)
    (target / "hooks").mkdir()
    (target / "hooks" / "hooks.json").write_text(json.dumps(HOOKS, indent=2) + "\n", encoding="utf-8")
    meta = target / ".claude-plugin"
    meta.mkdir()
    (meta / "plugin.json").write_text(json.dumps({
        "name": "forgemyspec", "version": VERSION,
        "description": "Spec-first development with chat approvals, deterministic gates and a requirements board.",
        "author": {"name": "Marlon Ferrari"},
    }, indent=2) + "\n", encoding="utf-8")
    (meta / "marketplace.json").write_text(json.dumps({
        "name": "forgemyspec", "owner": {"name": "Marlon Ferrari"},
        "metadata": {"description": "ForgeMySpec: spec-first development for Claude Code."},
        "plugins": [{"name": "forgemyspec", "source": "./", "description": "Spec-first development with deterministic gates."}],
    }, indent=2) + "\n", encoding="utf-8")
    (target / "tests").mkdir()
    (target / "tests" / "test_plugin.py").write_text(SMOKE_TEST, encoding="utf-8")
    (target / "README.md").write_text(README.format(path=target, version=VERSION), encoding="utf-8")
    (target / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")


if __name__ == "__main__":
    out = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else ROOT / "plugin"
    build(out)
    print(out)
