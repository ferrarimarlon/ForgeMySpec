from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (puts src/ on sys.path)

from forgemyspec.install import install


def run(target: Path, check: bool = False):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = install(target, check=check)
    return code, out.getvalue()


class InitTests(unittest.TestCase):
    def test_install_merge_idempotent_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            target.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=target, check=True)
            (target / ".claude").mkdir()
            (target / ".claude" / "settings.json").write_text(json.dumps({
                "permissions": {"allow": ["Bash(npm *)"]},
                "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo my-hook"}]}]},
                "defaultAgent": "forgemyspec-default",
            }), encoding="utf-8")
            (target / "CLAUDE.md").write_text("# My project\n\nMy rules.\n", encoding="utf-8")
            (target / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\necho old\n", encoding="utf-8")
            (target / ".claude" / "settings.local.json").write_text(json.dumps({
                "env": {"X": "1"},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 -m forgemyspec hook stop"}]}]},
            }), encoding="utf-8")

            code, out = run(target)
            self.assertEqual(code, 0, out)
            self.assertIn("strict mode", out)

            settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["agent"], "forgemyspec-default")
            self.assertNotIn("defaultAgent", settings)
            self.assertEqual(settings["permissions"], {"allow": ["Bash(npm *)"]})
            commands = [h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
            self.assertIn("echo my-hook", commands)
            ours = [h for e in settings["hooks"]["PreToolUse"] for h in e["hooks"] if "forgemyspec hook" in h["command"]]
            self.assertEqual(len(ours), 1)
            self.assertEqual(ours[0]["onFailure"], "block")
            for event in ("Stop", "SessionStart", "UserPromptSubmit"):
                self.assertTrue(any("forgemyspec hook" in h["command"] for e in settings["hooks"][event] for h in e["hooks"]))

            local = json.loads((target / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
            self.assertEqual(local, {"env": {"X": "1"}})  # our old hook removed, the user's settings kept

            claude = (target / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertTrue(claude.startswith("# My project\n\nMy rules.\n"))
            self.assertIn("<!-- forgemyspec:start -->", claude)
            self.assertIn("echo old", (target / ".githooks" / "pre-commit.local").read_text(encoding="utf-8"))
            self.assertTrue(os.access(target / ".githooks" / "pre-commit", os.X_OK))
            hooks_path = subprocess.run(["git", "config", "core.hooksPath"], cwd=target, capture_output=True, text=True).stdout.strip()
            self.assertEqual(hooks_path, ".githooks")
            for path in (".forgemyspec/harness/forgemyspec/_kernel/KernelImpl.py", ".forgemyspec/config.yaml",
                         ".claude/skills/forgemyspec/SKILL.md", ".claude/agents/forgemyspec-default.md",
                         ".github/workflows/forgemyspec.yml"):
                self.assertTrue((target / path).exists(), path)
            self.assertTrue(any((target / ".forgemyspec" / "backups").rglob("settings.json")))

            code, out = run(target)
            self.assertEqual((code, out.strip()), (0, "Installation is up to date; nothing changed."))
            self.assertEqual(run(target, check=True)[0], 0)

            settings["hooks"].pop("Stop")
            (target / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
            code, out = run(target, check=True)
            self.assertEqual(code, 1)
            self.assertIn(".claude/settings.json", out)

    def test_refuses_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(Path(tmp))[0], 1)


if __name__ == "__main__":
    unittest.main()
