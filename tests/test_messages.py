from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import copy_example_bundle, make_project

from forgemyspec import hooks, messages as M, risk
from forgemyspec.bundle import BundleLayout
from forgemyspec.contract_lock import check_lock
from forgemyspec.dafny_lint import lint_bundle_dafny
from forgemyspec.gate import format_gate_report, run_gate
from forgemyspec.linting import format_lint_report, lint_spec
from forgemyspec.spec_io import load_spec

PORTUGUESE = re.compile(
    r"\b(não|nao|é|está|para|com|sem|uma|um|que|de|da|dos|das|ou|seu|sua|você|ainda|"
    r"erro|falhou|passou|bloqueado|caminho|requisitos?|furando|frágil|provado|aprovad[oa]|travad[oa])\b"
    r"|[ãõçáéíóúâê]",
    re.IGNORECASE,
)


def _portuguese(text: str):
    found = []
    for line in text.splitlines():
        if line.strip().startswith(M.TOOL_PREFIX.strip()):
            continue
        without_code = re.sub(r"`[^`]*`|https?://\S+", "", line)
        found += [(m.group(0), line) for m in PORTUGUESE.finditer(without_code)]
    return found


def _texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _texts(v)


class MessagesTests(unittest.TestCase):
    def assertEnglish(self, text: str, origin: str) -> None:
        self.assertEqual(_portuguese(text), [], f"non-English text in {origin}")

    def test_all_output_in_english(self) -> None:
        # 1. The whole catalog.
        for name, value in vars(M).items():
            if name.isupper():
                for text in _texts(value):
                    self.assertEnglish(text, f"messages.{name}")

        # 2. Real output of every module.
        bad = {"version": "0.1", "title": "", "context": {"system": ""}, "hypotheses": [{"id": "h1", "description": "Does not work.", "confidence": 2}],
               "actions": [{"id": "a1", "type": "x", "supports": ["h9"]}], "formal": {"module": "1x", "obligations": [{"id": "Bad"}]},
               "metadata": {"scope_contract": {"must_include": ["phrase"]}}}
        self.assertEnglish(format_lint_report(lint_spec(bad, require_formal=True)), "lint")
        self.assertEnglish(format_lint_report(lint_spec(None)), "empty lint")

        with tempfile.TemporaryDirectory() as tmp:
            bundle = copy_example_bundle(Path(tmp))
            layout = BundleLayout.at(bundle)
            spec = load_spec(str(layout.spec))
            (layout.planted / "no_target.dfy").write_text("assume false;\n", encoding="utf-8")
            layout.impl.write_text(layout.impl.read_text(encoding="utf-8").replace("final := start;", "assume true; expect true; final := start;"))
            self.assertEnglish("\n".join(i.message for i in lint_bundle_dafny(layout, spec)), "Dafny lint")
            self.assertEnglish("\n".join(i.message for i in check_lock(layout, spec)), "lock")
            with patch.dict(os.environ, {"FORGEMYSPEC_DAFNY": str(Path(tmp) / "no-dafny")}):
                self.assertEnglish(format_gate_report(run_gate(str(bundle), write_cache=False)), "gate")

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}):
                for name, data in (("Write", {"file_path": str(root / "lib" / "x.py"), "content": "x"}),
                                   ("Write", {"file_path": str(root / "budget-core" / "contract.lock"), "content": "x"}),
                                   ("Edit", {"file_path": str(root / "budget-core" / "contract.dfy"), "old_string": "a", "new_string": "b"}),
                                   ("Write", {"file_path": str(root / "draft" / "x.py"), "content": "x"}),
                                   ("Bash", {"command": "python3 -m forgemyspec lock budget-core"}),
                                   ("Bash", {"command": "git commit --no-verify -m x"}),
                                   ("Bash", {"command": "echo x > lib/new.py"})):
                    answer = hooks.pre_tool_use({"tool_name": name, "cwd": str(root), "tool_input": data})
                    self.assertEnglish(answer["hookSpecificOutput"]["permissionDecisionReason"], f"guard {name}")
                self.assertEqual(hooks.stop({"cwd": str(root), "session_id": "s"}), {})
                self.assertEnglish(hooks.session_start({"cwd": str(root)})["hookSpecificOutput"]["additionalContext"], "state")
                self.assertEnglish(risk.render(risk.build(root)), "risk box")

        from forgemyspec.install import install

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                install(Path(tmp))
                install(Path(tmp), check=True)
            self.assertEnglish(out.getvalue(), "init")

        from forgemyspec.__main__ import build_parser

        self.assertEnglish(build_parser().format_help(), "--help")


if __name__ == "__main__":
    unittest.main()
