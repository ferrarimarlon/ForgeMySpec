from __future__ import annotations

import unittest

from support import make_valid_spec_data

from forgemyspec.scope_eval import evaluate_scope_drift


class ScopeEvalTests(unittest.TestCase):
    def test_scope_eval_detects_missing_required_scope(self) -> None:
        spec_data = make_valid_spec_data()
        candidate_text = "Build only argument parsing support and add a database-backed history feature."

        result = evaluate_scope_drift(spec_data, candidate_text)

        self.assertFalse(result.passed)
        self.assertEqual(result.score, 75)
        self.assertTrue(any("missing required scope phrase" in violation for violation in result.violations))

    def test_scope_eval_is_case_and_accent_insensitive(self) -> None:
        spec_data = make_valid_spec_data()
        spec_data["metadata"]["scope_contract"] = {
            "must_include": ["análise"],
            "must_not_include": ["banco de dados"],
        }

        result = evaluate_scope_drift(spec_data, "Inclui ANALISE, sem outro escopo.")

        self.assertTrue(result.passed)
        self.assertEqual(result.score, 100)


if __name__ == "__main__":
    unittest.main()
