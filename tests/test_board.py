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
        self.assertEqual(act["per"]["R1"], {"runs": 2, "writes": 1, "tokens": 0})
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

    def test_verified_only_by_a_passing_check(self) -> None:
        import json

        from forgemyspec import approvals

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            (root / board.PROJECT_BOARD_FILE).write_text(
                "- id: R1\n  status: doing\n  title: One\n  waiting: your go\n  steps:\n"
                "  - {do: passes, check: 'cmd: true'}\n  - {do: fails, check: 'cmd: false'}\n"
                "  - {do: said so, ok: true}\n  - {do: later}\n", encoding="utf-8")
            board.start(root, "R1")
            transcript = Path(tmp) / "t.jsonl"
            usage = {"output_tokens": 1500, "input_tokens": 10, "cache_read_input_tokens": 120000}
            transcript.write_text(json.dumps({"type": "assistant", "timestamp": approvals._now(),
                                              "message": {"id": "m", "usage": usage, "content": []}}) + "\n")
            approvals.remember_transcript(root, "s", str(transcript))
            r1 = board.load(root)[0]
            before = [board.step_state(x, board._checks(root), board.fingerprint(root)) for x in r1["steps"]]
            ran = board.verify(root)
            fp = board.fingerprint(root)
            after = [board.step_state(x, board._checks(root), fp) for x in r1["steps"]]
            text = board.render(root)
            detail = board.detail(root, "R1")
            (root / "app" / "main.py").write_text("print('changed')\n", encoding="utf-8")
            stale = board.step_state(r1["steps"][0], board._checks(root), board.fingerprint(root))
        self.assertEqual(before, ["todo", "todo", "claimed", "todo"])
        self.assertEqual([ok for *_, ok in ran], [True, False])
        self.assertEqual(after, ["verified", "failed", "claimed", "todo"])
        self.assertEqual(stale, "stale")
        self.assertIn("25%  ✔ verified by checks (1/4 steps)", text)
        self.assertIn("25%  ? claimed, no check (1)", text)
        self.assertIn("NOW       R1 One", text)
        self.assertIn("WAITING   R1 your go", text)
        self.assertIn("memory    context 120k tokens", text)
        self.assertIn("✔1 ✗1 ?1 ·1", text)
        self.assertIn("2k", text)
        self.assertIn("✗ fails  [cmd: false]", detail)


if __name__ == "__main__":
    unittest.main()
