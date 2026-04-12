from __future__ import annotations

import json
from typing import Any, Dict

from .nlp_policy import CompilerPolicy


SPEC_DRAFT_SCHEMA: Dict[str, Any] = {
    "title": "string",
    "objective": "string",
    "context": {
        "system": "string",
        "assumptions": ["string"],
    },
    "constraints": ["string"],
    "success_criteria": ["string"],
    "hypotheses": [
        {
            "id": "string_optional",
            "description": "string",
            "confidence": 0.5,
        }
    ],
    "required_evidence": ["string"],
    "actions": [
        {
            "id": "string_optional",
            "description": "string",
            "type": "string",
            "requires_confirmation": False,
            "supports": ["hypothesis_id"],
        }
    ],
    "decision_rules": ["string"],
    "metadata": {
        "profile": "string_optional",
        "scope_contract": {
            "must_include": ["string"],
            "must_not_include": ["string"],
        },
    },
}


def build_generation_system_prompt(profile: str | None, policy: CompilerPolicy) -> str:
    profile_instruction = (
        f"Use metadata.profile='{profile}' exactly. " if profile else "Set metadata.profile only when strongly implied by the prompt. "
    )

    action_type_instruction = (
        "Action `type` must be one of: " + ", ".join(sorted(policy.allowed_action_types)) + ". "
        if policy.allowed_action_types
        else "Action `type` should be concise and reusable (e.g., analyze, design, implement, validate, review). "
    )

    return (
        "You are a deterministic intent compiler for coding agents. "
        "Convert the user's free-form request into a strict operational specification in JSON. "
        "Output JSON only. No markdown and no explanation. "
        "Do not invent features outside the prompt. "
        "When details are missing, create explicit assumptions. "
        "Make success criteria testable and evidence-oriented. "
        "Every action must link to one or more hypotheses using the `supports` field. "
        "Mark `requires_confirmation=true` for destructive or high-risk actions. "
        "Include metadata.scope_contract.must_include and must_not_include as short enforceable phrases. "
        f"{profile_instruction}"
        f"{action_type_instruction}"
        f"Minimum section counts: {json.dumps(policy.min_items, sort_keys=True)}. "
        f"Schema: {json.dumps(SPEC_DRAFT_SCHEMA, ensure_ascii=True)}"
    )
