from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_valid_draft

from forgemyspec.generator import build_spec, load_spec, spec_to_yaml, write_spec
from forgemyspec.llm import LLMError, LLMProvider, LLMSettings
from forgemyspec.nlp_policy import CompilerPolicy
from forgemyspec.templates import build_generation_system_prompt


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, draft):
        self._draft = draft

    def generate_json(self, prompt: str, system_prompt: str):
        return self._draft


class GeneratorTests(unittest.TestCase):
    def test_build_spec_normalizes_ids_lists_and_metadata(self) -> None:
        policy = CompilerPolicy(allowed_action_types={"implement", "validate"})
        draft = make_valid_draft()

        spec = build_spec(
            "build a parser cli",
            profile="cli",
            llm_settings=LLMSettings(provider="openai", model="test-model"),
            llm_provider=FakeProvider(draft),
            policy=policy,
        )

        self.assertEqual(spec.version, "0.1")
        self.assertEqual(spec.execution_mode, "step_by_step")
        self.assertEqual(spec.context.assumptions, ["The user wants a command-line interface."])
        self.assertEqual([item.id for item in spec.hypotheses], ["parser", "parser_2"])
        self.assertEqual([item.id for item in spec.actions], ["implement_parser", "validate_cli"])
        self.assertEqual(spec.actions[0].type, "implement")
        self.assertEqual(spec.actions[0].supports, ["parser"])
        self.assertEqual(spec.actions[1].supports, ["parser_2"])
        self.assertEqual(spec.metadata["source_prompt"], "build a parser cli")
        self.assertEqual(spec.metadata["generator"], "llm-fake")
        self.assertEqual(spec.metadata["model"], "test-model")
        self.assertEqual(spec.metadata["profile"], "cli")
        self.assertEqual(
            spec.metadata["scope_contract"],
            {
                "must_include": ["parser cli", "argument parsing"],
            },
        )

    def test_build_spec_rejects_unknown_support_links(self) -> None:
        policy = CompilerPolicy(allowed_action_types={"implement"})
        draft = make_valid_draft()
        draft["actions"] = [
            {
                "id": "implement parser",
                "description": "Implement the parser module.",
                "type": "implement",
                "requires_confirmation": False,
                "supports": ["missing_hypothesis"],
            }
        ]

        with self.assertRaises(LLMError):
            build_spec(
                "build a parser cli",
                llm_settings=LLMSettings(provider="openai", model="test-model"),
                llm_provider=FakeProvider(draft),
                policy=policy,
            )

    def test_spec_yaml_round_trip(self) -> None:
        draft = make_valid_draft()
        spec = build_spec(
            "build a parser cli",
            llm_settings=LLMSettings(provider="openai", model="test-model"),
            llm_provider=FakeProvider(draft),
            policy=CompilerPolicy(allowed_action_types={"implement", "validate"}),
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            spec_path = Path(tmp_dir) / "spec.yaml"
            write_spec(spec, str(spec_path))
            loaded = load_spec(str(spec_path))

        self.assertEqual(loaded["title"], spec.title)
        self.assertEqual(loaded["metadata"]["source_prompt"], "build a parser cli")
        self.assertIn("objective:", spec_to_yaml(spec))

    def test_generation_system_prompt_reflects_policy(self) -> None:
        policy = CompilerPolicy(
            allowed_action_types={"analyze", "implement"},
            min_items={"actions": 2, "hypotheses": 1},
        )

        prompt = build_generation_system_prompt(profile="cli", policy=policy)

        self.assertIn("metadata.profile='cli'", prompt)
        self.assertIn("Action `type` must be one of: analyze, implement.", prompt)
        self.assertIn('"actions": 2', prompt)


if __name__ == "__main__":
    unittest.main()
