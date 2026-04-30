from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_valid_spec_data

from forgemyspec.claude_skill import package_claude_skill
from forgemyspec.generator import write_spec
from forgemyspec.models import Action, Context, Hypothesis, Spec


def _build_spec() -> Spec:
    spec_data = make_valid_spec_data()
    return Spec(
        version=spec_data["version"],
        title=spec_data["title"],
        objective=spec_data["objective"],
        context=Context(**spec_data["context"]),
        constraints=spec_data["constraints"],
        success_criteria=spec_data["success_criteria"],
        hypotheses=[Hypothesis(**item) for item in spec_data["hypotheses"]],
        required_evidence=spec_data["required_evidence"],
        actions=[Action(**item) for item in spec_data["actions"]],
        decision_rules=spec_data["decision_rules"],
        execution_mode=spec_data["execution_mode"],
        metadata=spec_data["metadata"],
    )


class ClaudeSkillTests(unittest.TestCase):
    def test_package_claude_skill_writes_expected_bundle(self) -> None:
        spec = _build_spec()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "bundle"
            output_dir.mkdir()
            source_spec_path = output_dir / "source-spec.yaml"
            write_spec(spec, str(source_spec_path))

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


if __name__ == "__main__":
    unittest.main()
