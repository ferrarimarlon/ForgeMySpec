from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Dict, List

from . import messages as M
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
        found = M.EMPTY_FILE if spec_data is None else type(spec_data).__name__
        add("error", "LINT-STRUCT-000", M.LINT["LINT-STRUCT-000"].format(found=found))
        return _build_report(issues, compiler_policy)

    _validate_required_structure(spec_data, add)

    context = spec_data.get("context") if isinstance(spec_data.get("context"), dict) else {}
    assumptions = context.get("assumptions") if isinstance(context.get("assumptions"), list) else []
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
        M.LINT_REPORT_SCORE.format(score=report.score),
        M.LINT_REPORT_ERRORS.format(n=report.error_count),
        M.LINT_REPORT_WARNINGS.format(n=report.warning_count),
    ]
    if not report.issues:
        lines.append(M.LINT_REPORT_CLEAN)
        return "\n".join(lines)

    lines.append(M.LINT_REPORT_ISSUES)
    for issue in report.issues:
        lines.append(
            f"- [{M.SEVERITY.get(issue.severity, issue.severity.upper())}] {issue.code} ({issue.location}) {issue.message}"
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
            add("error", "LINT-STRUCT-001", M.LINT["LINT-STRUCT-001"].format(field=field), field)
            continue
        if not isinstance(spec_data[field], expected_type):
            add(
                "error",
                "LINT-STRUCT-002",
                M.LINT["LINT-STRUCT-002"].format(field=field, type=expected_type.__name__),
                field,
            )

    context = spec_data.get("context")
    if isinstance(context, dict):
        if not isinstance(context.get("system"), str) or not context.get("system", "").strip():
            add("error", "LINT-CTX-002", M.LINT["LINT-CTX-002"], "context.system")
        if not isinstance(context.get("assumptions"), list):
            add("error", "LINT-CTX-003", M.LINT["LINT-CTX-003"], "context.assumptions")


def _validate_min_items(field: str, values: List[Any], add, policy: CompilerPolicy) -> None:
    minimum = policy.min_items.get(field, 0)
    if len(values) < minimum:
        add(
            "error",
            "LINT-MIN-001",
            M.LINT["LINT-MIN-001"].format(field=field, minimum=minimum, received=len(values)),
            field,
        )


def _validate_hypotheses(hypotheses: List[Any], add) -> None:
    ids = set()
    for index, item in enumerate(hypotheses, start=1):
        location = f"hypotheses[{index}]"
        if not isinstance(item, dict):
            add("error", "LINT-HY-001", M.LINT["LINT-HY-001"], location)
            continue

        hypothesis_id = item.get("id")
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            add("error", "LINT-HY-002", M.LINT["LINT-HY-002"], f"{location}.id")
        elif hypothesis_id in ids:
            add("error", "LINT-HY-003", M.LINT["LINT-HY-003"], f"{location}.id")
        else:
            ids.add(hypothesis_id)

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            add("error", "LINT-HY-004", M.LINT["LINT-HY-004"], f"{location}.description")

        confidence = item.get("confidence")
        if not isinstance(confidence, (float, int)):
            add("error", "LINT-HY-005", M.LINT["LINT-HY-005"], f"{location}.confidence")
        elif confidence < 0 or confidence > 1:
            add("error", "LINT-HY-006", M.LINT["LINT-HY-006"], f"{location}.confidence")


def _validate_actions(actions: List[Any], add, policy: CompilerPolicy) -> None:
    ids = set()

    for index, item in enumerate(actions, start=1):
        location = f"actions[{index}]"
        if not isinstance(item, dict):
            add("error", "LINT-ACT-001", M.LINT["LINT-ACT-001"], location)
            continue

        action_id = item.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            add("error", "LINT-ACT-002", M.LINT["LINT-ACT-002"], f"{location}.id")
        elif action_id in ids:
            add("error", "LINT-ACT-003", M.LINT["LINT-ACT-003"], f"{location}.id")
        else:
            ids.add(action_id)

        action_type = item.get("type")
        if not isinstance(action_type, str) or not action_type.strip():
            add("error", "LINT-ACT-004", M.LINT["LINT-ACT-004"], f"{location}.type")
        elif policy.allowed_action_types and action_type.lower() not in policy.allowed_action_types:
            add(
                "warning",
                "LINT-ACT-005",
                M.LINT["LINT-ACT-005"].format(type=action_type),
                f"{location}.type",
            )

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            add("error", "LINT-ACT-006", M.LINT["LINT-ACT-006"], f"{location}.description")

        requires_confirmation = item.get("requires_confirmation")
        if not isinstance(requires_confirmation, bool):
            add(
                "error",
                "LINT-ACT-007",
                M.LINT["LINT-ACT-007"],
                f"{location}.requires_confirmation",
            )

        supports = item.get("supports")
        if policy.require_action_support_links:
            if not isinstance(supports, list) or not supports:
                add(
                    "error",
                    "LINT-ACT-008",
                    M.LINT["LINT-ACT-008"],
                    f"{location}.supports",
                )
            elif not all(isinstance(entry, str) and entry.strip() for entry in supports):
                add(
                    "error",
                    "LINT-ACT-009",
                    M.LINT["LINT-ACT-009"],
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
                    M.LINT["LINT-TR-001"].format(id=entry),
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
                M.LINT["LINT-TR-002"].format(id=hypothesis_id),
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
                M.LINT["LINT-META-001"].format(field=key),
                f"metadata.{key}",
            )


_NEGATION_WORDS = {"not", "no", "never", "without", "excluding", "avoid", "avoids", "excluded", "omit", "omits"}
# In Portuguese "no" is the contraction of "em + o"; negation uses these words.
_NEGATION_WORDS_PT = {"nao", "nunca", "sem", "exceto", "evitar", "evita", "evitam", "jamais", "nenhum", "nenhuma", "omitir", "omite", "excluir", "exclui"}
_FUNCTION_WORDS_PT = {"de", "que", "um", "uma", "e", "os", "as", "do", "da", "dos", "das", "para", "com", "em", "pelo", "pela", "ao", "se", "ou", "quando"}
_FUNCTION_WORDS_EN = {"the", "of", "and", "to", "is", "are", "a", "an", "for", "with", "that", "when", "by", "be"}
_EVIDENCE_NOISE_PREFIXES = ("source code", "the source code", "codebase", "the codebase", "implementation", "the implementation")


def _validate_execution_mode(spec_data: Dict[str, Any], add) -> None:
    mode = spec_data.get("execution_mode")
    if isinstance(mode, str) and mode.strip() and mode.strip() != "critical":
        add(
            "warning",
            "LINT-STRUCT-003",
            M.LINT["LINT-STRUCT-003"].format(mode=mode.strip()),
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
        portuguese = len(words & _FUNCTION_WORDS_PT) > len(words & _FUNCTION_WORDS_EN)
        if words & (_NEGATION_WORDS_PT if portuguese else _NEGATION_WORDS):
            add(
                "warning",
                "LINT-HY-007",
                M.LINT["LINT-HY-007"],
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
            M.LINT["LINT-TR-003"].format(type=action_type, total=len(hypothesis_ids), ids=ids_str),
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
                M.LINT["LINT-EV-001"],
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
            add("error", "LINT-FORMAL-000", M.LINT["LINT-FORMAL-000"], "formal")
        return
    if not isinstance(formal, dict):
        add("error", "LINT-FORMAL-001", M.LINT["LINT-FORMAL-001/mapping"], "formal")
        return

    module = formal.get("module")
    if not isinstance(module, str) or not _DAFNY_IDENTIFIER.match(module.strip()):
        add("error", "LINT-FORMAL-001", M.LINT["LINT-FORMAL-001/module"], "formal.module")

    obligations = formal.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        add("error", "LINT-FORMAL-001", M.LINT["LINT-FORMAL-001/list"], "formal.obligations")
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
            add("error", "LINT-FORMAL-002", M.LINT["LINT-FORMAL-002/object"], location)
            continue

        obligation_id = item.get("id")
        if not isinstance(obligation_id, str) or not _OBLIGATION_ID.match(obligation_id):
            add("error", "LINT-FORMAL-002", M.LINT["LINT-FORMAL-002/format"], f"{location}.id")
        elif obligation_id in seen_ids:
            add("error", "LINT-FORMAL-002", M.LINT["LINT-FORMAL-002/duplicate"].format(id=obligation_id), f"{location}.id")
        else:
            seen_ids.add(obligation_id)

        statement = item.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            add("error", "LINT-FORMAL-009", M.LINT["LINT-FORMAL-009"], f"{location}.statement")

        kind = item.get("kind")
        if kind not in OBLIGATION_KINDS:
            add("error", "LINT-FORMAL-003", M.LINT["LINT-FORMAL-003"].format(kinds=list(OBLIGATION_KINDS)), f"{location}.kind")
        elif kind == "boundary":
            test = item.get("test")
            if not isinstance(test, str) or not test.strip():
                add("error", "LINT-FORMAL-006", M.LINT["LINT-FORMAL-006"], f"{location}.test")

        refs = item.get("hypotheses")
        if not isinstance(refs, list) or not refs:
            add("error", "LINT-FORMAL-004", M.LINT["LINT-FORMAL-004/empty"], f"{location}.hypotheses")
        else:
            for ref in refs:
                if ref not in hypothesis_ids:
                    add("error", "LINT-FORMAL-004", M.LINT["LINT-FORMAL-004/unknown"].format(id=ref), f"{location}.hypotheses")
                else:
                    covered_hypotheses.add(ref)

        phrases = item.get("must_include", [])
        if not isinstance(phrases, list):
            add("error", "LINT-FORMAL-005", M.LINT["LINT-FORMAL-005/list"], f"{location}.must_include")
            continue
        for phrase in phrases:
            if phrase not in must_include:
                add(
                    "error",
                    "LINT-FORMAL-005",
                    M.LINT["LINT-FORMAL-005/phrase"].format(phrase=phrase),
                    f"{location}.must_include",
                )
            else:
                covered_phrases.add(phrase)

    # Coverage comes from the proven kernel (TrustKernel.Coverage).
    from . import kernel

    valid = [o for o in obligations if isinstance(o, dict)]
    missing_h, missing_p = kernel.coverage(
        sorted(hypothesis_ids),
        must_include,
        [[r for r in o.get("hypotheses") or [] if isinstance(r, str)] for o in valid],
        [[p for p in o.get("must_include") or [] if isinstance(p, str)] if isinstance(o.get("must_include"), list) else [] for o in valid],
    )
    for hypothesis_id in missing_h:
        add("error", "LINT-FORMAL-007", M.LINT["LINT-FORMAL-007"].format(id=hypothesis_id), "formal.obligations")
    for phrase in missing_p:
        add("error", "LINT-FORMAL-008", M.LINT["LINT-FORMAL-008"].format(phrase=phrase), "formal.obligations")


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
            M.LINT["LINT-DUP-001"].format(field=field),
            field,
        )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()
