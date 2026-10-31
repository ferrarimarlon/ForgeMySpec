from __future__ import annotations

import unittest

import copy

from support import EXAMPLE_BUNDLE, make_valid_spec_data

from forgemyspec.spec_io import load_spec

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

    def test_lint_spec_reports_non_mapping_instead_of_crashing(self) -> None:
        for value in (None, [], "text"):
            report = lint_spec(value)
            self.assertTrue(report.has_errors)
            self.assertEqual(report.issues[0].code, "LINT-STRUCT-000")


class FormalCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = load_spec(str(EXAMPLE_BUNDLE / "spec.yaml"))

    def codes(self, spec, require_formal: bool = True) -> set:
        return {issue.code for issue in lint_spec(spec, require_formal=require_formal).issues}

    def test_example_bundle_has_full_coverage(self) -> None:
        report = lint_spec(self.spec, require_formal=True)
        self.assertEqual(report.issues, [])

    def test_missing_formal_section_fails_only_when_required(self) -> None:
        spec = copy.deepcopy(self.spec)
        del spec["formal"]
        self.assertIn("LINT-FORMAL-000", self.codes(spec))
        self.assertNotIn("LINT-FORMAL-000", self.codes(spec, require_formal=False))

    def test_uncovered_must_include_phrase_fails(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["metadata"]["scope_contract"]["must_include"].append("audit log of every rejection")
        self.assertIn("LINT-FORMAL-008", self.codes(spec))

    def test_uncovered_hypothesis_fails(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["hypotheses"].append({"id": "h9", "description": "Exports work as CSV.", "confidence": 0.5})
        spec["actions"][-1]["supports"].append("h9")
        self.assertIn("LINT-FORMAL-007", self.codes(spec))

    def test_paraphrased_must_include_is_not_accepted(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["formal"]["obligations"][0]["must_include"] = ["deposits add the exact amount"]
        codes = self.codes(spec)
        self.assertIn("LINT-FORMAL-005", codes)
        self.assertIn("LINT-FORMAL-008", codes)

    def test_boundary_obligation_needs_a_test(self) -> None:
        spec = copy.deepcopy(self.spec)
        boundary = next(item for item in spec["formal"]["obligations"] if item["kind"] == "boundary")
        del boundary["test"]
        self.assertIn("LINT-FORMAL-006", self.codes(spec))

    def test_duplicate_and_malformed_obligation_ids_fail(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["formal"]["obligations"][1]["id"] = spec["formal"]["obligations"][0]["id"]
        spec["formal"]["obligations"][2]["id"] = "Bad-Id"
        spec["formal"]["obligations"][3]["kind"] = "prose"
        codes = self.codes(spec)
        self.assertIn("LINT-FORMAL-002", codes)
        self.assertIn("LINT-FORMAL-003", codes)


if __name__ == "__main__":
    unittest.main()
