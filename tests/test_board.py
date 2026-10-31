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


if __name__ == "__main__":
    unittest.main()
