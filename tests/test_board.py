from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import SRC  # noqa: F401  (puts src on sys.path)

from forgemyspec import board

BOARD = """
- id: R1
  status: doing
  title: First requirement
  quote: the user's words
  steps:
  - {do: passing check, check: "cmd: true"}
  - {do: failing check, check: "cmd: false"}
  - {do: only claimed, ok: true}
  - {do: not done yet}
- id: R2
  status: done
  title: Second requirement
  steps:
  - {do: claimed only, ok: true}
"""


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        (self.root / "forgemyspec-board.yaml").write_text(BOARD)
        (self.root / "code.py").write_text("x = 1\n")
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verified_only_by_a_passing_check_and_stale_after_a_change(self):
        board.verify(self.root)
        results, fp = board._checks(self.root), board.fingerprint(self.root)
        states = [board.step_state(s, results, fp) for s in board.load(self.root)[0]["steps"]]
        self.assertEqual(states, ["verified", "failed", "claimed", "todo"])
        (self.root / "code.py").write_text("x = 2\n")
        fp = board.fingerprint(self.root)
        self.assertEqual(board.step_state(board.load(self.root)[0]["steps"][0], results, fp), "stale")

    def test_board_change_does_not_make_checks_stale(self):
        board.verify(self.root)
        before = board.fingerprint(self.root)
        (self.root / "forgemyspec-board.yaml").write_text(BOARD + "\n")
        self.assertEqual(before, board.fingerprint(self.root))

    def test_render_shows_status_harness_and_model_shares(self):
        board.verify(self.root)
        text = board.render(self.root)
        self.assertIn("ForgeMySpec · 2 requirements", text)
        self.assertIn("1/2", text)
        self.assertIn("harness", text)
        self.assertIn("✔ verified by checks (1/5 steps)", text)
        self.assertIn("? claimed, no check (2)", text)
        self.assertIn("done without a check: R2", text)

    def test_activity_counts_harness_runs_model_writes_and_tokens_in_focus(self):
        transcript = self.root / "t.jsonl"
        board.start(self.root, "R1")
        entries = [
            {"type": "assistant", "timestamp": "2999-01-01T00:00:00.000Z",
             "message": {"id": "m1", "usage": {"output_tokens": 1000, "input_tokens": 5, "cache_read_input_tokens": 9000},
                         "content": [{"type": "tool_use", "name": "Bash",
                                      "input": {"command": "PYTHONPATH=src python3 -m forgemyspec.board verify"}},
                                     {"type": "tool_use", "name": "Write", "input": {}}]}},
            {"type": "assistant", "timestamp": "2999-01-01T00:00:01.000Z",
             "message": {"id": "m2", "usage": {"output_tokens": 500},
                         "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}},
        ]
        transcript.write_text("\n".join(json.dumps(e) for e in entries))
        board.hook_stop({"cwd": str(self.root), "transcript_path": str(transcript), "stop_hook_active": True})
        act = board.activity(self.root)
        self.assertEqual((act["runs"], act["writes"], act["tokens"]), (1, 1, 1500))
        self.assertEqual(act["context"], 9005)
        self.assertEqual(board.effort(act, "R1"), "H 50% M 50%")

    def test_stop_hook_sends_a_reply_without_the_board_back_once(self):
        event = {"cwd": str(self.root), "last_assistant_message": "done, no board"}
        self.assertEqual(board.hook_stop(event)["decision"], "block")
        self.assertEqual(board.hook_stop(dict(event, stop_hook_active=True)), {})
        with_board = dict(event, last_assistant_message="ForgeMySpec · 2 requirements\n...")
        self.assertEqual(board.hook_stop(with_board), {})


if __name__ == "__main__":
    unittest.main()
