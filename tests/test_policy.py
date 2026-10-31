from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

import support  # noqa: F401  (puts src/ on sys.path)

from forgemyspec.nlp_policy import PolicyConfigError, load_compiler_policy


class PolicyTests(unittest.TestCase):
    def test_load_compiler_policy_applies_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_path = Path(tmp_dir) / "policy.yaml"
            policy_path.write_text(
                textwrap.dedent(
                    """
                    min_items:
                      actions: 3
                      hypotheses: 2
                    allowed_action_types:
                      - implement
                      - validate
                    lint_min_passing_score: 80
                    mutation_min_kill_rate: 0.75
                    max_mutants: 12
                    dafny_min_version: "4.2"
                    required_metadata_fields:
                      - source_prompt
                      - generator
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            policy = load_compiler_policy(str(policy_path))

        self.assertEqual(policy.min_items["actions"], 3)
        self.assertEqual(policy.min_items["hypotheses"], 2)
        self.assertEqual(policy.allowed_action_types, {"implement", "validate"})
        self.assertEqual(policy.lint_min_passing_score, 80)
        self.assertEqual(policy.required_metadata_fields, {"source_prompt", "generator"})
        self.assertEqual(policy.mutation_min_kill_rate, 0.75)
        self.assertEqual(policy.max_mutants, 12)
        self.assertEqual(policy.dafny_min_version, "4.2")

    def test_load_compiler_policy_rejects_invalid_kill_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_path = Path(tmp_dir) / "policy.yaml"
            policy_path.write_text("mutation_min_kill_rate: 1.5\n", encoding="utf-8")
            with self.assertRaises(PolicyConfigError):
                load_compiler_policy(str(policy_path))


if __name__ == "__main__":
    unittest.main()
