from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from support import make_project

from forgemyspec import project
from forgemyspec.__main__ import main


class PanelTests(unittest.TestCase):
    def test_risk_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            config = project.load_config(root)
            budget = next(b for b in project.discover_bundles(root, config) if b.name == "budget-core")
            project.write_gate_cache(budget, config, {"passed": True, "stages": [], "evidence": {}, "tier": "fast"})
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(["risk", "--json"]), 0)
            data = json.loads(out.getvalue())

        self.assertEqual(set(data), {"requirements", "met", "bundles", "lines", "leaks", "leak_count", "human", "turn"})
        self.assertEqual(data["met"], sum(1 for r in data["requirements"] if r["status"] != "leaking"))
        replay = next(r for r in data["requirements"] if r["phrase"] == "ledger replay")
        self.assertEqual(replay["bundle"], "budget-core")
        self.assertTrue(replay["obligations"][0]["statement"])
        budget_state = next(b for b in data["bundles"] if b["name"] == "budget-core")
        self.assertEqual((budget_state["gate"], budget_state["tier"], budget_state["formal"]), ("pass", "fast", True))
        self.assertEqual(set(data["lines"]), {"proven", "examples", "free"})
        self.assertEqual(set(data["turn"]), {"files", "lines", "free", "guard_checks", "blocked", "gates"})


if __name__ == "__main__":
    unittest.main()
