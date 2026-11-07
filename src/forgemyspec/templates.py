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
    "execution_mode": "critical",
    "metadata": {
        "profile": "string_optional",
        "scope_contract": {
            "must_include": ["string — critical functional requirement, security constraint, or non-negotiable behavior"],
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
        "required_evidence items must be observable outputs — runnable examples, test results, or concrete console/log outputs. Never list source code or the implementation itself as evidence. "
        "Every action must link to one or more hypotheses using the `supports` field. "
        "Mark `requires_confirmation=true` for destructive or high-risk actions. "
        "Set execution_mode to 'critical' for all specs — treat every spec as a high-stakes contract. "
        "Hypotheses must be affirmative and testable statements about what will work — never state what will NOT be built; those belong in constraints. "
        "Each hypothesis must be verifiable through evidence or a concrete test, not a declaration of intent. "
        "metadata.scope_contract.must_include must contain short enforceable phrases covering: critical functional requirements, security and safety constraints, and non-negotiable behaviors. "
        "Do NOT add must_not_include — out-of-scope items belong in constraints. "
        f"{profile_instruction}"
        f"{action_type_instruction}"
        f"Minimum section counts: {json.dumps(policy.min_items, sort_keys=True)}. "
        f"Schema: {json.dumps(SPEC_DRAFT_SCHEMA, ensure_ascii=True)}"
    )
