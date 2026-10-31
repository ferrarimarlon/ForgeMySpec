from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Set

import yaml

from . import messages as M


DEFAULT_POLICY_FILE = ".forgemyspec-policy.yaml"


class PolicyConfigError(RuntimeError):
    pass


@dataclass
class CompilerPolicy:
    min_items: Dict[str, int] = field(
        default_factory=lambda: {
            "assumptions": 1,
            "constraints": 1,
            "success_criteria": 1,
            "hypotheses": 1,
            "required_evidence": 1,
            "actions": 1,
            "decision_rules": 1,
        }
    )
    allowed_action_types: Set[str] = field(default_factory=set)
    require_action_support_links: bool = True
    required_metadata_fields: Set[str] = field(default_factory=lambda: {"source_prompt"})
    scope_contract_field: str = "scope_contract"
    lint_base_score: int = 100
    lint_error_penalty: int = 18
    lint_warning_penalty: int = 5
    lint_min_passing_score: int = 70
    scope_eval_base_score: int = 100
    scope_violation_penalty: int = 25
    mutation_min_kill_rate: float = 0.9
    max_mutants: int = 40
    dafny_min_version: str = "4.0"
    dafny_timeout_seconds: int = 300
    min_planted_errors: int = 3


def load_compiler_policy(path: str | None = None) -> CompilerPolicy:
    policy = CompilerPolicy()

    for candidate in _candidate_paths(path):
        if not candidate.exists():
            continue
        data = _safe_load_yaml(candidate)
        if data is None:
            raise PolicyConfigError(M.POLICY["yaml"].format(path=candidate))
        _apply_overrides(policy, data)
        break

    return policy


def _candidate_paths(path: str | None) -> list[Path]:
    ordered: list[Path] = []
    if path:
        ordered.append(Path(path))
    env_path = os.getenv("FORGEMYSPEC_POLICY") or os.getenv("FORGEMYSPEC_NLP_POLICY")
    if env_path:
        ordered.append(Path(env_path))
    ordered.append(Path.cwd() / DEFAULT_POLICY_FILE)
    return ordered


def _safe_load_yaml(path: Path) -> Dict[str, Any] | None:
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        loaded = yaml.safe_load(payload)
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _apply_overrides(policy: CompilerPolicy, data: Dict[str, Any]) -> None:
    min_items = data.get("min_items")
    if min_items is not None:
        if not isinstance(min_items, dict):
            raise PolicyConfigError(M.POLICY["min_items"])
        normalized: Dict[str, int] = {}
        for key, value in min_items.items():
            if not isinstance(key, str) or not isinstance(value, int) or value < 0:
                raise PolicyConfigError(M.POLICY["min_items_values"])
            normalized[key.strip()] = value
        if normalized:
            policy.min_items = normalized

    allowed_action_types = data.get("allowed_action_types")
    if allowed_action_types is not None:
        if not isinstance(allowed_action_types, list):
            raise PolicyConfigError(M.POLICY["allowed_action_types"])
        cleaned = {str(item).strip().lower() for item in allowed_action_types if str(item).strip()}
        policy.allowed_action_types = cleaned

    require_links = data.get("require_action_support_links")
    if require_links is not None:
        if not isinstance(require_links, bool):
            raise PolicyConfigError(M.POLICY["require_action_support_links"])
        policy.require_action_support_links = require_links

    required_metadata_fields = data.get("required_metadata_fields")
    if required_metadata_fields is not None:
        if not isinstance(required_metadata_fields, list):
            raise PolicyConfigError(M.POLICY["required_metadata_fields"])
        cleaned_fields = {str(item).strip() for item in required_metadata_fields if str(item).strip()}
        policy.required_metadata_fields = cleaned_fields

    scope_contract_field = data.get("scope_contract_field")
    if scope_contract_field is not None:
        if not isinstance(scope_contract_field, str) or not scope_contract_field.strip():
            raise PolicyConfigError(M.POLICY["scope_contract_field"])
        policy.scope_contract_field = scope_contract_field.strip()

    _set_int(policy, "lint_base_score", data.get("lint_base_score"), minimum=1)
    _set_int(policy, "lint_error_penalty", data.get("lint_error_penalty"), minimum=0)
    _set_int(policy, "lint_warning_penalty", data.get("lint_warning_penalty"), minimum=0)
    _set_int(policy, "lint_min_passing_score", data.get("lint_min_passing_score"), minimum=0)
    _set_int(policy, "scope_eval_base_score", data.get("scope_eval_base_score"), minimum=1)
    _set_int(policy, "scope_violation_penalty", data.get("scope_violation_penalty"), minimum=0)
    _set_int(policy, "max_mutants", data.get("max_mutants"), minimum=1)
    _set_int(policy, "dafny_timeout_seconds", data.get("dafny_timeout_seconds"), minimum=1)
    _set_int(policy, "min_planted_errors", data.get("min_planted_errors"), minimum=0)

    kill_rate = data.get("mutation_min_kill_rate")
    if kill_rate is not None:
        if isinstance(kill_rate, bool) or not isinstance(kill_rate, (int, float)) or not 0 <= kill_rate <= 1:
            raise PolicyConfigError(M.POLICY["kill_rate"])
        policy.mutation_min_kill_rate = float(kill_rate)

    min_version = data.get("dafny_min_version")
    if min_version is not None:
        if not isinstance(min_version, str) or not re.fullmatch(r"\d+(\.\d+)*", min_version.strip()):
            raise PolicyConfigError(M.POLICY["dafny_min_version"])
        policy.dafny_min_version = min_version.strip()


def _set_int(policy: CompilerPolicy, attr: str, value: Any, minimum: int) -> None:
    if value is None:
        return
    if not isinstance(value, int):
        raise PolicyConfigError(M.POLICY["integer"].format(field=attr))
    if value < minimum:
        raise PolicyConfigError(M.POLICY["minimum"].format(field=attr, minimum=minimum))
    setattr(policy, attr, value)
