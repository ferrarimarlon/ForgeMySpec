from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any, Dict, List

from .nlp_policy import CompilerPolicy, load_compiler_policy


@dataclass
class ScopeEvalResult:
    score: int
    violations: List[str]

    @property
    def passed(self) -> bool:
        return not self.violations


def evaluate_scope_drift(
    spec_data: Dict[str, Any],
    candidate_text: str,
    policy: CompilerPolicy | None = None,
) -> ScopeEvalResult:
    compiler_policy = policy or load_compiler_policy()

    contract = _extract_scope_contract(spec_data, compiler_policy.scope_contract_field)
    candidate = _normalize_text(candidate_text)

    violations: List[str] = []

    for phrase in contract.get("must_include", []):
        normalized_phrase = _normalize_text(phrase)
        if normalized_phrase and normalized_phrase not in candidate:
            violations.append(f"Candidate missing required scope phrase: '{phrase}'")

    score = max(
        0,
        compiler_policy.scope_eval_base_score
        - (len(violations) * compiler_policy.scope_violation_penalty),
    )
    return ScopeEvalResult(score=score, violations=violations)


def format_scope_eval(result: ScopeEvalResult) -> str:
    lines = [f"Scope eval score: {result.score}/100"]
    if result.passed:
        lines.append("No scope-drift violations detected.")
        return "\n".join(lines)

    lines.append("Violations:")
    for violation in result.violations:
        lines.append(f"- {violation}")
    return "\n".join(lines)


def _extract_scope_contract(spec_data: Dict[str, Any], field_name: str) -> Dict[str, List[str]]:
    metadata = spec_data.get("metadata") if isinstance(spec_data.get("metadata"), dict) else {}
    contract = metadata.get(field_name) if isinstance(metadata, dict) else None
    if not isinstance(contract, dict):
        return {"must_include": []}

    return {
        "must_include": _coerce_list(contract.get("must_include")),
    }


def _coerce_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()
