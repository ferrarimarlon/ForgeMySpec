from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT

from forgemyspec.branding import _provider_label
from forgemyspec.config import load_default_dotenvs, load_dotenv
from forgemyspec.llm import LLMError, LLMSettings, build_provider
from forgemyspec.nlp_policy import load_compiler_policy


class ConfigAndPolicyTests(unittest.TestCase):
    def test_load_dotenv_reads_values_and_overwrites_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("NEW_KEY=value\nEXISTING_KEY=from_file\n", encoding="utf-8")

            with patch.dict(os.environ, {"EXISTING_KEY": "from_env"}, clear=False):
                loaded = load_dotenv(str(env_path))
                self.assertTrue(loaded)
                self.assertEqual(os.environ["NEW_KEY"], "value")
                self.assertEqual(os.environ["EXISTING_KEY"], "from_file")

    def test_load_default_dotenvs_reads_only_local_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            (tmp_root / ".env").write_text("LOCAL_ONLY=1\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                previous_cwd = Path.cwd()
                try:
                    os.chdir(tmp_root)
                    loaded = load_default_dotenvs()
                    loaded_value = os.environ.get("LOCAL_ONLY")
                finally:
                    os.chdir(previous_cwd)

            self.assertTrue(loaded)
            self.assertEqual(loaded_value, "1")

    def test_load_default_dotenvs_does_not_search_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            nested = tmp_root / "src" / "forgemyspec"
            nested.mkdir(parents=True)
            (tmp_root / ".env").write_text('OPENAI_MODEL="gpt-5.5"\n', encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                previous_cwd = Path.cwd()
                try:
                    os.chdir(nested)
                    loaded = load_default_dotenvs()
                    loaded_value = os.environ.get("OPENAI_MODEL")
                finally:
                    os.chdir(previous_cwd)

            self.assertFalse(loaded)
            self.assertIsNone(loaded_value)

    def test_provider_label_uses_exact_model_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "gpt-5.5"},
            clear=True,
        ):
            label, _color = _provider_label()

        self.assertEqual(label, "gpt-5.5  OpenAI")

    def test_openai_provider_requires_model_when_key_is_present(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            provider = build_provider(LLMSettings(provider="openai"))

            with self.assertRaisesRegex(LLMError, "OPENAI_MODEL is not configured."):
                provider.generate_json("hello", "system")

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


if __name__ == "__main__":
    unittest.main()
