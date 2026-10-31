from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Dict, List

from .nlp_policy import CompilerPolicy, load_compiler_policy


@dataclass
class LintIssue:
    severity: str
    code: str
    message: str
    location: str = "spec"


@dataclass
class LintReport:
    issues: List[LintIssue]
    error_count: int
    warning_count: int
    score: int

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0


def lint_spec(
    spec_data: Any,
    policy: CompilerPolicy | None = None,
    require_formal: bool = False,
) -> LintReport:
    compiler_policy = policy or load_compiler_policy()
    issues: List[LintIssue] = []

    def add(severity: str, code: str, message: str, location: str = "spec") -> None:
        issues.append(LintIssue(severity=severity, code=code, message=message, location=location))

    if not isinstance(spec_data, dict):
        found = "empty file" if spec_data is None else type(spec_data).__name__
        add("error", "LINT-STRUCT-000", f"Spec must be a YAML mapping; found {found}")
        return _build_report(issues, compiler_policy)

    _validate_required_structure(spec_data, add)

    context = spec_data.get("context") if isinstance(spec_data.get("context"), dict) else {}
    assumptions = context.get("assumptions") if isinstance(context, dict) else []
    actions = spec_data.get("actions") if isinstance(spec_data.get("actions"), list) else []
    hypotheses = spec_data.get("hypotheses") if isinstance(spec_data.get("hypotheses"), list) else []
    constraints = spec_data.get("constraints") if isinstance(spec_data.get("constraints"), list) else []
    success_criteria = spec_data.get("success_criteria") if isinstance(spec_data.get("success_criteria"), list) else []
    required_evidence = spec_data.get("required_evidence") if isinstance(spec_data.get("required_evidence"), list) else []
    decision_rules = spec_data.get("decision_rules") if isinstance(spec_data.get("decision_rules"), list) else []

    _validate_min_items("assumptions", assumptions, add, compiler_policy)
    _validate_min_items("constraints", constraints, add, compiler_policy)
    _validate_min_items("success_criteria", success_criteria, add, compiler_policy)
    _validate_min_items("hypotheses", hypotheses, add, compiler_policy)
    _validate_min_items("required_evidence", required_evidence, add, compiler_policy)
    _validate_min_items("actions", actions, add, compiler_policy)
    _validate_min_items("decision_rules", decision_rules, add, compiler_policy)

    _validate_execution_mode(spec_data, add)
    _validate_hypotheses(hypotheses, add)
    _validate_hypotheses_quality(hypotheses, add)
    _validate_actions(actions, add, compiler_policy)
    _validate_traceability_links(actions, hypotheses, add, compiler_policy)
    _validate_traceability_breadth(actions, hypotheses, add)
    _validate_evidence_quality(required_evidence, add)
    _validate_metadata(spec_data, add, compiler_policy)

    _warn_duplicates(constraints, add, "constraints")
    _warn_duplicates(success_criteria, add, "success_criteria")
    _warn_duplicates(required_evidence, add, "required_evidence")
    _warn_duplicates(decision_rules, add, "decision_rules")

    _validate_formal(spec_data, hypotheses, add, compiler_policy, require_formal)

    return _build_report(issues, compiler_policy)


def _build_report(issues: List[LintIssue], compiler_policy: CompilerPolicy) -> LintReport:
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    score = max(
        0,
        compiler_policy.lint_base_score
        - (error_count * compiler_policy.lint_error_penalty)
        - (warning_count * compiler_policy.lint_warning_penalty),
    )

    return LintReport(
        issues=issues,
        error_count=error_count,
        warning_count=warning_count,
        score=score,
    )


def format_lint_report(report: LintReport) -> str:
    lines = [
        f"Lint score: {report.score}/100",
        f"Errors: {report.error_count}",
        f"Warnings: {report.warning_count}",
    ]
    if not report.issues:
        lines.append("No issues found.")
        return "\n".join(lines)

    lines.append("Issues:")
    for issue in report.issues:
        lines.append(
            f"- [{issue.severity.upper()}] {issue.code} ({issue.location}) {issue.message}"
        )
    return "\n".join(lines)


def _validate_required_structure(spec_data: Dict[str, Any], add) -> None:
    required = {
        "version": str,
        "title": str,
        "objective": str,
        "context": dict,
        "constraints": list,
        "success_criteria": list,
        "hypotheses": list,
        "required_evidence": list,
        "actions": list,
        "decision_rules": list,
        "execution_mode": str,
        "metadata": dict,
    }
    for field, expected_type in required.items():
        if field not in spec_data:
            add("error", "LINT-STRUCT-001", f"Missing required field: {field}", field)
            continue
        if not isinstance(spec_data[field], expected_type):
            add(
                "error",
                "LINT-STRUCT-002",
                f"Invalid type for {field}: expected {expected_type.__name__}",
                field,
            )

    context = spec_data.get("context")
    if isinstance(context, dict):
        if not isinstance(context.get("system"), str) or not context.get("system", "").strip():
            add("error", "LINT-CTX-002", "context.system must be a non-empty string", "context.system")
        if not isinstance(context.get("assumptions"), list):
            add("error", "LINT-CTX-003", "context.assumptions must be a list", "context.assumptions")


def _validate_min_items(field: str, values: List[Any], add, policy: CompilerPolicy) -> None:
    minimum = policy.min_items.get(field, 0)
    if len(values) < minimum:
        add(
            "error",
            "LINT-MIN-001",
            f"Field '{field}' must have at least {minimum} item(s); received {len(values)}",
            field,
        )


def _validate_hypotheses(hypotheses: List[Any], add) -> None:
    ids = set()
    for index, item in enumerate(hypotheses, start=1):
        location = f"hypotheses[{index}]"
        if not isinstance(item, dict):
            add("error", "LINT-HY-001", "Hypothesis entry must be an object", location)
            continue

        hypothesis_id = item.get("id")
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            add("error", "LINT-HY-002", "Hypothesis id must be a non-empty string", f"{location}.id")
        elif hypothesis_id in ids:
            add("error", "LINT-HY-003", "Hypothesis ids must be unique", f"{location}.id")
        else:
            ids.add(hypothesis_id)

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            add("error", "LINT-HY-004", "Hypothesis description must be non-empty", f"{location}.description")

        confidence = item.get("confidence")
        if not isinstance(confidence, (float, int)):
            add("error", "LINT-HY-005", "Hypothesis confidence must be numeric", f"{location}.confidence")
        elif confidence < 0 or confidence > 1:
            add("error", "LINT-HY-006", "Hypothesis confidence must be between 0 and 1", f"{location}.confidence")


def _validate_actions(actions: List[Any], add, policy: CompilerPolicy) -> None:
    ids = set()

    for index, item in enumerate(actions, start=1):
        location = f"actions[{index}]"
        if not isinstance(item, dict):
            add("error", "LINT-ACT-001", "Action entry must be an object", location)
            continue

        action_id = item.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            add("error", "LINT-ACT-002", "Action id must be a non-empty string", f"{location}.id")
        elif action_id in ids:
            add("error", "LINT-ACT-003", "Action ids must be unique", f"{location}.id")
        else:
            ids.add(action_id)

        action_type = item.get("type")
        if not isinstance(action_type, str) or not action_type.strip():
            add("error", "LINT-ACT-004", "Action type must be a non-empty string", f"{location}.type")
        elif policy.allowed_action_types and action_type.lower() not in policy.allowed_action_types:
            add(
                "warning",
                "LINT-ACT-005",
                f"Action type '{action_type}' is outside policy allowed_action_types",
                f"{location}.type",
            )

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            add("error", "LINT-ACT-006", "Action description must be non-empty", f"{location}.description")

        requires_confirmation = item.get("requires_confirmation")
        if not isinstance(requires_confirmation, bool):
            add(
                "error",
                "LINT-ACT-007",
                "Action requires_confirmation must be a boolean",
                f"{location}.requires_confirmation",
            )

        supports = item.get("supports")
        if policy.require_action_support_links:
            if not isinstance(supports, list) or not supports:
                add(
                    "error",
                    "LINT-ACT-008",
                    "Action supports must be a non-empty list of hypothesis ids",
                    f"{location}.supports",
                )
            elif not all(isinstance(entry, str) and entry.strip() for entry in supports):
                add(
                    "error",
                    "LINT-ACT-009",
                    "Action supports entries must be non-empty strings",
                    f"{location}.supports",
                )


def _validate_traceability_links(actions: List[Any], hypotheses: List[Any], add, policy: CompilerPolicy) -> None:
    hypothesis_ids = {
        item.get("id")
        for item in hypotheses
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id").strip()
    }

    linked: set[str] = set()
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            continue
        supports = action.get("supports")
        if not isinstance(supports, list):
            continue
        for entry in supports:
            if not isinstance(entry, str) or not entry.strip():
                continue
            if entry not in hypothesis_ids:
                add(
                    "error",
                    "LINT-TR-001",
                    f"Action references unknown hypothesis id: {entry}",
                    f"actions[{index}].supports",
                )
            else:
                linked.add(entry)

    if policy.require_action_support_links:
        missing = sorted(hypothesis_ids - linked)
        for hypothesis_id in missing:
            add(
                "warning",
                "LINT-TR-002",
                f"Hypothesis is not linked by any action: {hypothesis_id}",
                "hypotheses",
            )


def _validate_metadata(spec_data: Dict[str, Any], add, policy: CompilerPolicy) -> None:
    metadata = spec_data.get("metadata") if isinstance(spec_data.get("metadata"), dict) else {}
    for key in sorted(policy.required_metadata_fields):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            add(
                "error",
                "LINT-META-001",
                f"metadata.{key} must be a non-empty string",
                f"metadata.{key}",
            )


_NEGATION_WORDS = {"not", "no", "never", "without", "excluding", "avoid", "avoids", "excluded", "omit", "omits"}
_EVIDENCE_NOISE_PREFIXES = ("source code", "the source code", "codebase", "the codebase", "implementation", "the implementation")


def _validate_execution_mode(spec_data: Dict[str, Any], add) -> None:
    mode = spec_data.get("execution_mode")
    if isinstance(mode, str) and mode.strip() and mode.strip() != "critical":
        add(
            "warning",
            "LINT-STRUCT-003",
            f"execution_mode is '{mode.strip()}'; expected 'critical' for high-stakes specs",
            "execution_mode",
        )


def _validate_hypotheses_quality(hypotheses: List[Any], add) -> None:
    for index, item in enumerate(hypotheses, start=1):
        if not isinstance(item, dict):
            continue
        description = item.get("description", "")
        if not isinstance(description, str):
            continue
        words = set(re.sub(r"[^a-z\s]", "", _normalize_text(description)).split())
        if words & _NEGATION_WORDS:
            add(
                "warning",
                "LINT-HY-007",
                "Hypothesis appears to describe what will NOT be built; hypotheses must be affirmative and testable",
                f"hypotheses[{index}].description",
            )


def _validate_traceability_breadth(actions: List[Any], hypotheses: List[Any], add) -> None:
    hypothesis_ids = {
        item.get("id")
        for item in hypotheses
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id").strip()
    }
    if len(hypothesis_ids) < 2:
        return
    _BROAD_ACTION_TYPES = {"validate", "review", "test"}

    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            continue
        supports = action.get("supports")
        if not isinstance(supports, list):
            continue
        linked = {e for e in supports if isinstance(e, str) and e.strip()}
        if not linked or not linked >= hypothesis_ids:
            continue
        action_type = (action.get("type") or "").strip().lower()
        if action_type in _BROAD_ACTION_TYPES:
            continue
        ids_str = ", ".join(sorted(hypothesis_ids))
        add(
            "warning",
            "LINT-TR-003",
            f"'{action_type}' action supports all {len(hypothesis_ids)} hypotheses ({ids_str}) — "
            f"each non-validation action should target only the hypotheses it directly advances",
            f"actions[{index}].supports",
        )


def _validate_evidence_quality(required_evidence: List[Any], add) -> None:
    for index, item in enumerate(required_evidence, start=1):
        if not isinstance(item, str):
            continue
        normalized = _normalize_text(item).strip()
        if any(normalized.startswith(prefix) for prefix in _EVIDENCE_NOISE_PREFIXES):
            add(
                "warning",
                "LINT-EV-001",
                "Evidence item describes an artifact, not an observable output; prefer runnable examples, test results, or concrete outputs",
                f"required_evidence[{index}]",
            )


_OBLIGATION_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_DAFNY_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
OBLIGATION_KINDS = ("dafny", "boundary")


def _validate_formal(
    spec_data: Dict[str, Any],
    hypotheses: List[Any],
    add,
    policy: CompilerPolicy,
    require_formal: bool,
) -> None:
    formal = spec_data.get("formal")
    if formal is None:
        if require_formal:
            add("error", "LINT-FORMAL-000", "Missing 'formal' section required by the Dafny gate", "formal")
        return
    if not isinstance(formal, dict):
        add("error", "LINT-FORMAL-001", "'formal' must be a mapping", "formal")
        return

    module = formal.get("module")
    if not isinstance(module, str) or not _DAFNY_IDENTIFIER.match(module.strip()):
        add("error", "LINT-FORMAL-001", "formal.module must be a Dafny identifier", "formal.module")

    obligations = formal.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        add("error", "LINT-FORMAL-001", "formal.obligations must be a non-empty list", "formal.obligations")
        return

    hypothesis_ids = {
        item.get("id")
        for item in hypotheses
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id").strip()
    }
    metadata = spec_data.get("metadata") if isinstance(spec_data.get("metadata"), dict) else {}
    contract = metadata.get(policy.scope_contract_field)
    must_include = _coerce_strings(contract.get("must_include")) if isinstance(contract, dict) else []

    seen_ids: set[str] = set()
    covered_hypotheses: set[str] = set()
    covered_phrases: set[str] = set()

    for index, item in enumerate(obligations, start=1):
        location = f"formal.obligations[{index}]"
        if not isinstance(item, dict):
            add("error", "LINT-FORMAL-002", "Obligation entry must be an object", location)
            continue

        obligation_id = item.get("id")
        if not isinstance(obligation_id, str) or not _OBLIGATION_ID.match(obligation_id):
            add("error", "LINT-FORMAL-002", "Obligation id must match [a-z][a-z0-9_]*", f"{location}.id")
        elif obligation_id in seen_ids:
            add("error", "LINT-FORMAL-002", f"Obligation id is not unique: {obligation_id}", f"{location}.id")
        else:
            seen_ids.add(obligation_id)

        statement = item.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            add("error", "LINT-FORMAL-009", "Obligation statement must be non-empty", f"{location}.statement")

        kind = item.get("kind")
        if kind not in OBLIGATION_KINDS:
            add("error", "LINT-FORMAL-003", f"Obligation kind must be one of {list(OBLIGATION_KINDS)}", f"{location}.kind")
        elif kind == "boundary":
            test = item.get("test")
            if not isinstance(test, str) or not test.strip():
                add("error", "LINT-FORMAL-006", "Boundary obligation must name its Python test id", f"{location}.test")

        refs = item.get("hypotheses")
        if not isinstance(refs, list) or not refs:
            add("error", "LINT-FORMAL-004", "Obligation must list the hypotheses it covers", f"{location}.hypotheses")
        else:
            for ref in refs:
                if ref not in hypothesis_ids:
                    add("error", "LINT-FORMAL-004", f"Obligation references unknown hypothesis id: {ref}", f"{location}.hypotheses")
                else:
                    covered_hypotheses.add(ref)

        phrases = item.get("must_include", [])
        if not isinstance(phrases, list):
            add("error", "LINT-FORMAL-005", "Obligation must_include must be a list", f"{location}.must_include")
            continue
        for phrase in phrases:
            if phrase not in must_include:
                add(
                    "error",
                    "LINT-FORMAL-005",
                    f"Obligation must_include entry is not an exact scope_contract.must_include phrase: {phrase!r}",
                    f"{location}.must_include",
                )
            else:
                covered_phrases.add(phrase)

    for hypothesis_id in sorted(hypothesis_ids - covered_hypotheses):
        add("error", "LINT-FORMAL-007", f"Hypothesis is not covered by any formal obligation: {hypothesis_id}", "formal.obligations")
    for phrase in must_include:
        if phrase not in covered_phrases:
            add("error", "LINT-FORMAL-008", f"must_include phrase is not covered by any formal obligation: {phrase!r}", "formal.obligations")


def _coerce_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _warn_duplicates(values: List[Any], add, field: str) -> None:
    seen = set()
    duplicates = set()
    for item in values:
        if not isinstance(item, str):
            continue
        key = re.sub(r"\s+", " ", _normalize_text(item)).strip()
        if not key:
            continue
        if key in seen:
            duplicates.add(item)
        seen.add(key)

    if duplicates:
        add(
            "warning",
            "LINT-DUP-001",
            f"Field '{field}' contains duplicate or near-duplicate entries",
            field,
        )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()
