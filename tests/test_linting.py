from __future__ import annotations

import unittest

from support import make_valid_spec_data

from forgemyspec.linting import lint_spec
from forgemyspec.nlp_policy import CompilerPolicy


class LintingTests(unittest.TestCase):
    def test_lint_spec_returns_clean_report_for_valid_spec(self) -> None:
        report = lint_spec(make_valid_spec_data())

        self.assertFalse(report.has_errors)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.score, 100)

    def test_lint_spec_flags_duplicates_and_missing_traceability(self) -> None:
        spec_data = make_valid_spec_data()
        spec_data["constraints"].append("Use only the standard library.")
        spec_data["actions"][1]["supports"] = ["missing_id"]

        report = lint_spec(spec_data)
        codes = {issue.code for issue in report.issues}

        self.assertTrue(report.has_errors)
        self.assertIn("LINT-TR-001", codes)
        self.assertIn("LINT-DUP-001", codes)
        self.assertLess(report.score, 100)

    def test_lint_spec_obeys_custom_policy(self) -> None:
        spec_data = make_valid_spec_data()
        spec_data["actions"][0]["type"] = "design"
        policy = CompilerPolicy(allowed_action_types={"implement", "validate"})

        report = lint_spec(spec_data, policy=policy)

        self.assertFalse(report.has_errors)
        self.assertEqual(report.warning_count, 1)
        self.assertEqual(report.issues[0].code, "LINT-ACT-005")


if __name__ == "__main__":
    unittest.main()
