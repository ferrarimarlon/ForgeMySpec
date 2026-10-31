"""Smoke test of the exported plugin: manifest, hooks and a guard decision."""

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
        self.assertEqual(set(hooks), {"PreToolUse", "SessionStart", "UserPromptSubmit"})

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
