from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def _normalize_identifier(value: str, fallback: str = "") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", _normalize_text(value)).strip("_")
    return normalized or fallback


def _coerce_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _coerce_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", _normalize_text(item.strip()))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(item)
    return ordered


class SpecModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Hypothesis(SpecModel):
    id: str
    description: str
    confidence: float

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        normalized = _normalize_identifier(value)
        if not normalized:
            raise ValueError("hypothesis id must be non-empty")
        return normalized

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        if not value:
            raise ValueError("hypothesis description must be non-empty")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.5
        return max(0.0, min(parsed, 1.0))

    @classmethod
    def from_draft(cls, value: Any, index: int, seen_ids: set[str]) -> Hypothesis | None:
        if not isinstance(value, dict):
            return None

        description = _coerce_text(value.get("description"))
        if not description:
            return None

        hypothesis_id = _normalize_identifier(_coerce_text(value.get("id")), fallback=f"h{index}")
        if hypothesis_id in seen_ids:
            hypothesis_id = _normalize_identifier(f"{hypothesis_id}_{index}", fallback=f"h{index}")
        seen_ids.add(hypothesis_id)

        return cls(
            id=hypothesis_id,
            description=description,
            confidence=value.get("confidence", 0.5),
        )


class Action(SpecModel):
    id: str
    description: str
    type: str
    requires_confirmation: bool = False
    supports: List[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        normalized = _normalize_identifier(value)
        if not normalized:
            raise ValueError("action id must be non-empty")
        return normalized

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        if not value:
            raise ValueError("action description must be non-empty")
        return value

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, value: Any) -> str:
        return _normalize_identifier(_coerce_text(value), fallback="action")

    @field_validator("supports", mode="before")
    @classmethod
    def _normalize_supports(cls, value: Any) -> List[str]:
        return [
            normalized
            for token in _coerce_list(value)
            for normalized in [_normalize_identifier(token)]
            if normalized
        ]

    @classmethod
    def from_draft(cls, value: Any, index: int, seen_ids: set[str]) -> Action | None:
        if not isinstance(value, dict):
            return None

        description = _coerce_text(value.get("description"))
        if not description:
            return None

        action_id = _normalize_identifier(_coerce_text(value.get("id")), fallback=f"a{index}")
        if action_id in seen_ids:
            action_id = _normalize_identifier(f"{action_id}_{index}", fallback=f"a{index}")
        seen_ids.add(action_id)

        return cls(
            id=action_id,
            description=description,
            type=value.get("type", "action"),
            requires_confirmation=bool(value.get("requires_confirmation", False)),
            supports=value.get("supports"),
        )


class Context(SpecModel):
    system: str
    assumptions: List[str] = Field(default_factory=list)

    @field_validator("system")
    @classmethod
    def _validate_system(cls, value: str) -> str:
        if not value:
            raise ValueError("context.system must be non-empty")
        return value

    @field_validator("assumptions", mode="before")
    @classmethod
    def _normalize_assumptions(cls, value: Any) -> List[str]:
        return _dedupe(_coerce_list(value))

    @classmethod
    def from_draft(cls, value: Any) -> Context:
        data = value if isinstance(value, dict) else {}
        return cls(
            system=_coerce_text(data.get("system")),
            assumptions=data.get("assumptions"),
        )


class Spec(SpecModel):
    version: str
    title: str
    objective: str
    context: Context
    constraints: List[str]
    success_criteria: List[str]
    hypotheses: List[Hypothesis]
    required_evidence: List[str]
    actions: List[Action]
    decision_rules: List[str]
    execution_mode: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "objective", "execution_mode")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        if not value:
            raise ValueError("field must be non-empty")
        return value

    @field_validator("constraints", "success_criteria", "required_evidence", "decision_rules", mode="before")
    @classmethod
    def _normalize_string_lists(cls, value: Any) -> List[str]:
        return _dedupe(_coerce_list(value))


class ActionState(SpecModel):
    id: str
    status: str = "pending"
    phase: str = "brief"
    evidence: List[str] = Field(default_factory=list)
    notes: str = ""


class ExecutionState(SpecModel):
    spec_title: str
    current_action_index: int = 0
    actions: List[ActionState] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
