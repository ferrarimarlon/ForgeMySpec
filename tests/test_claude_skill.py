from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_valid_spec_data

from forgemyspec.claude_skill import package_claude_skill
from forgemyspec.spec_io import write_spec


class ClaudeSkillTests(unittest.TestCase):
    def test_package_claude_skill_writes_expected_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "bundle"
            output_dir.mkdir()
            source_spec_path = output_dir / "source-spec.yaml"
            write_spec(make_valid_spec_data(), str(source_spec_path))

            result = package_claude_skill(str(source_spec_path), str(output_dir))

            self.assertTrue(Path(result.spec_path).exists())
            self.assertTrue(Path(result.memory_path).exists())
            self.assertTrue(Path(result.command_path).exists())
            self.assertTrue(Path(result.checklist_path).exists())
            self.assertTrue(Path(result.eval_template_path).exists())

            memory = Path(result.memory_path).read_text(encoding="utf-8")
            checklist = Path(result.checklist_path).read_text(encoding="utf-8")
            command = Path(result.command_path).read_text(encoding="utf-8")
            eval_template = Path(result.eval_template_path).read_text(encoding="utf-8")

        self.assertIn("Build a parser CLI", memory)
        self.assertIn("Non-Negotiable Guardrails", memory)
        self.assertIn("Objective implemented exactly", checklist)
        self.assertIn("Implement strictly from `./spec.yaml`", command)
        self.assertIn("must_include", eval_template)
        self.assertIn("parser cli", eval_template)

    def test_repackaging_keeps_decisions_and_pitfalls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            spec_path = Path(tmp_dir) / "spec.yaml"
            write_spec(make_valid_spec_data(), str(spec_path))
            result = package_claude_skill(str(spec_path), tmp_dir)
            memory = Path(result.memory_path)
            text = memory.read_text(encoding="utf-8")
            text = text.replace("- (record stable architecture or policy decisions here)", "- Decision A.")
            text = text.replace("- (record recurring implementation failure modes here)", "- Pitfall B.")
            memory.write_text(text, encoding="utf-8")

            spec = make_valid_spec_data()
            spec["title"] = "Build a parser CLI, revised"
            write_spec(spec, str(spec_path))
            package_claude_skill(str(spec_path), tmp_dir)
            again = memory.read_text(encoding="utf-8")

        self.assertIn("Build a parser CLI, revised", again)
        self.assertIn("## Decision Log\n- Decision A.", again)
        self.assertIn("## Known Pitfalls\n- Pitfall B.", again)


if __name__ == "__main__":
    unittest.main()
