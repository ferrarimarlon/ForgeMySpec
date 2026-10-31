from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from support import make_project

from forgemyspec import board


class BoardTests(unittest.TestCase):
    def test_bars_and_detail(self) -> None:
        self.assertEqual(board.bar(1, 4, 8), "██░░░░░░")
        self.assertEqual(board.bar(0, 0, 4), "░░░░")
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            (root / board.BOARD_FILE).parent.mkdir(parents=True)
            (root / board.BOARD_FILE).write_text(
                "- {id: R01, status: done, title: First, quote: primeiro}\n"
                "- {id: R02, status: doing, title: Second}\n", encoding="utf-8")
            first = board.render(root)
            again = board.render(root)
            detail = board.detail(root, "r01")
        self.assertIn("ForgeMySpec · 2 requirements", first)
        self.assertIn("1/2", first)
        self.assertIn("changed:", first)
        self.assertNotIn("changed:", again)
        self.assertIn("you said: primeiro", detail)

    def test_present_in_every_installed_project(self) -> None:
        from forgemyspec import messages as M
        from forgemyspec.install import CLAUDE_BLOCK
        from forgemyspec.project import DEFAULT_CONFIG

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            (root / board.PROJECT_BOARD_FILE).write_text("- {id: R1, status: open, title: Only}\n", encoding="utf-8")
            self.assertIn("ForgeMySpec · 1 requirements", board.render(root))
        self.assertIn("forgemyspec board", M.STATE_RULES)
        self.assertIn("forgemyspec board", CLAUDE_BLOCK)
        self.assertIn("forgemyspec-board.yaml", DEFAULT_CONFIG["allow_paths"])
        skill = Path(__file__).resolve().parents[1] / "plugins" / "forgemyspec" / "skills" / "forgemyspec-board" / "SKILL.md"
        self.assertTrue(skill.exists())

    def test_effort_is_attributed_to_the_requirement_in_focus(self) -> None:
        import json

        from forgemyspec import approvals

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            (root / board.PROJECT_BOARD_FILE).write_text(
                "- {id: R1, status: doing, title: One, steps: [{do: a, ok: true}, {do: b, ok: false}]}\n", encoding="utf-8")
            transcript = Path(tmp) / "t.jsonl"
            board.start(root, "r1")
            later = approvals._now()
            calls = [{"type": "tool_use", "name": "Bash", "input": {"command": "python3 -m forgemyspec gate x"}},
                     {"type": "tool_use", "name": "Bash", "input": {"command": "python3 -m unittest"}},
                     {"type": "tool_use", "name": "Write", "input": {"file_path": "a.py"}}]
            transcript.write_text(json.dumps({"type": "assistant", "timestamp": later,
                                              "message": {"id": "m1", "content": calls}}) + "\n", encoding="utf-8")
            approvals.remember_transcript(root, "s", str(transcript))
            act = board.activity(root)
            text = board.render(root)
        self.assertEqual(act["per"]["R1"], {"runs": 2, "writes": 1})
        self.assertIn("H 67% M 33%", text)
        self.assertIn(" 50%", text)

    def test_stop_hook_sends_back_a_reply_without_the_board_once(self) -> None:
        from forgemyspec import hooks

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            base = {"cwd": str(root), "session_id": "s"}
            self.assertEqual(hooks.stop(dict(base, last_assistant_message="no board")), {})  # no board file: silent
            (root / board.PROJECT_BOARD_FILE).write_text("- {id: R1, status: open, title: One}\n", encoding="utf-8")
            missing = hooks.stop(dict(base, last_assistant_message="done, see above"))
            present = hooks.stop(dict(base, last_assistant_message="ok\n```\nForgeMySpec · 1 requirements\n```"))
            again = hooks.stop(dict(base, last_assistant_message="still none", stop_hook_active=True))
        self.assertEqual(missing["decision"], "block")
        self.assertIn("forgemyspec board", missing["reason"])
        self.assertEqual(present, {})
        self.assertEqual(again, {})


if __name__ == "__main__":
    unittest.main()
