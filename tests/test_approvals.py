from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import yaml

from support import make_project

from forgemyspec import approvals, hooks, project
from forgemyspec.__main__ import main


def _say(transcript: Path, entry: dict) -> None:
    with transcript.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _human(text: str) -> dict:
    return {"type": "user", "origin": {"kind": "human"}, "timestamp": approvals._now(),
            "message": {"role": "user", "content": text}}


class ApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self._tmp.name))
        self.transcript = Path(self._tmp.name) / "session.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        approvals.remember_transcript(self.root, "s1", str(self.transcript))
        env = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        terminal = mock.patch.object(approvals, "is_terminal", return_value=False)
        terminal.start()
        self.addCleanup(terminal.stop)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _check(self) -> approvals.Verdict:
        return approvals.check(self.root, "approve", "draft-spec", terminal=False)

    def _cli(self, *argv: str) -> int:
        # Bundle paths resolve against the working directory, as when the user runs the command in the project.
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
                code = main(list(argv))
        finally:
            os.chdir(cwd)
        self.last_error = err.getvalue()
        return code

    def _bash(self, command: str):
        config = project.load_config(self.root)
        return hooks.decide_bash(self.root, config, project.discover_bundles(self.root, config), command, self.root)

    def test_chat_approval_flow(self) -> None:
        _say(self.transcript, _human("an early message"))
        code, records = approvals.request(self.root, [("approve", "draft-spec")])
        self.assertRegex(code, r"^[A-Z2-7]{6}$")
        self.assertEqual(records[0]["target"], "draft-spec")

        # Nothing typed yet: refused, and the CLI and the Bash guard refuse too.
        self.assertEqual(self._check().reason, "no-typed-code")
        self.assertEqual(self._cli("approve", "draft-spec"), 1)
        allow, reason = self._bash("PYTHONPATH=src python3 -m forgemyspec approve draft-spec")
        self.assertFalse(allow)
        self.assertIn("request-approval approve:draft-spec", reason)

        # The code in Claude's own message, in a tool result or in a skill load is not the user's approval.
        stamp = approvals._now()
        _say(self.transcript, {"type": "assistant", "timestamp": stamp, "message": {"content": [{"type": "text", "text": code}]}})
        _say(self.transcript, {"type": "user", "origin": {"kind": "human"}, "timestamp": stamp,
                               "message": {"content": [{"type": "tool_result", "content": code}]}})
        _say(self.transcript, dict(_human(code), isMeta=True))
        _say(self.transcript, {"type": "user", "timestamp": stamp, "message": {"content": code}})
        self.assertEqual(self._check().reason, "no-typed-code")

        # The user types the code: approved, and the guard lets the command through.
        _say(self.transcript, _human(f"Approved: {code.lower()}"))
        self.assertTrue(self._check().approved)
        self.assertEqual(self._bash("python3 -m forgemyspec approve draft-spec"), (True, ""))

        # The content changes after the approval: refused until it is back to what was approved.
        spec = self.root / "draft-spec" / "spec.yaml"
        original = spec.read_text(encoding="utf-8")
        spec.write_text(original.replace("Build a parser CLI", "Build another CLI"), encoding="utf-8")
        verdict = self._check()
        self.assertEqual((verdict.approved, verdict.reason, verdict.code), (False, "content-changed", code))
        self.assertEqual(self._cli("approve", "draft-spec"), 1)
        spec.write_text(original, encoding="utf-8")

        # The CLI consumes the approval and records it in the lock.
        self.assertEqual(self._cli("approve", "draft-spec"), 0)
        lock = yaml.safe_load((self.root / "draft-spec" / "spec.lock").read_text(encoding="utf-8"))
        self.assertEqual((lock["approved_via"], lock["approval_code"]), ("chat", code))

        # One approval, one use.
        self.assertEqual(self._check().reason, "already-used")
        self.assertEqual(self._cli("approve", "draft-spec"), 1)
        self.assertFalse(self._bash("python3 -m forgemyspec approve draft-spec")[0])

    def test_code_typed_before_the_request_does_not_count(self) -> None:
        code, _ = approvals.request(self.root, [("approve", "draft-spec")])
        _say(self.transcript, dict(_human(code), timestamp="2000-01-01T00:00:00.000Z"))
        self.assertEqual(self._check().reason, "no-typed-code")

    def test_message_sent_mid_turn_counts(self) -> None:
        code, _ = approvals.request(self.root, [("approve", "draft-spec")])
        _say(self.transcript, {"type": "attachment", "timestamp": approvals._now(),
                               "attachment": {"type": "queued_command", "origin": {"kind": "human"}, "prompt": code}})
        self.assertTrue(self._check().approved)

    def test_code_cannot_be_moved_to_other_items(self) -> None:
        code, _ = approvals.request(self.root, [("approve", "app-spec")])
        _say(self.transcript, _human(code))
        state = project.state_dir(self.root) / approvals.APPROVALS_FILE
        data = json.loads(state.read_text(encoding="utf-8"))
        item = data["requests"][0]["items"][0]
        item["target"], item["content_sha"] = "draft-spec", approvals.content_sha(self.root, "approve", "draft-spec")
        state.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self._check().reason, "no-typed-code")

    def test_init_hashes_the_harness_the_command_runs(self) -> None:
        import shutil

        from forgemyspec.install import PACKAGE

        copy = Path(self._tmp.name) / "harness" / "forgemyspec"
        shutil.copytree(PACKAGE, copy, ignore=shutil.ignore_patterns("__pycache__"))
        same = approvals.content_sha(self.root, "init", ".", copy)
        self.assertEqual(same, approvals.content_sha(self.root, "init", "."))
        (copy / "messages.py").write_text("# changed\n", encoding="utf-8")
        self.assertNotEqual(approvals.content_sha(self.root, "init", ".", copy), same)

    def test_terminal_is_an_approval(self) -> None:
        self.assertTrue(approvals.check(self.root, "approve", "draft-spec", terminal=True).approved)

    def test_one_code_covers_every_item_of_the_request(self) -> None:
        code, _ = approvals.request(self.root, [("approve", "draft-spec"), ("lock", "budget-core")])
        _say(self.transcript, _human(code))
        self.assertTrue(self._check().approved)
        self.assertTrue(approvals.check(self.root, "lock", "budget-core", terminal=False).approved)
        self.assertEqual(self._cli("request-approval", "deploy:budget-core"), 1)

    def test_transcripts_and_user_settings_are_protected(self) -> None:
        config = project.load_config(self.root)
        bundles = project.discover_bundles(self.root, config)
        claude = Path.home() / ".claude"
        for path in (claude / "projects" / "x" / "s.jsonl", claude / "settings.json", claude / "settings.local.json"):
            allow, _ = hooks.decide_path(self.root, config, bundles, path, "Write", {"content": "x"})
            self.assertFalse(allow, path)
        allow, _ = self._bash(f"echo forged >> {claude / 'projects' / 'x' / 's.jsonl'}")
        self.assertFalse(allow)


if __name__ == "__main__":
    unittest.main()
