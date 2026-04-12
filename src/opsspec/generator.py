from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from .llm import LLMError, LLMProvider, LLMSettings, build_provider
from .models import Action, Context, Hypothesis, Spec
from .nlp_policy import CompilerPolicy, load_compiler_policy
from .templates import build_generation_system_prompt


DEFAULT_VERSION = "0.1"


def build_spec(
    prompt: str,
    execution_mode: str = "step_by_step",
    profile: Optional[str] = None,
    llm_settings: Optional[LLMSettings] = None,
    llm_provider: Optional[LLMProvider] = None,
    policy: Optional[CompilerPolicy] = None,
) -> Spec:
    prompt = prompt.strip()
    if not prompt:
        raise LLMError("Prompt is empty.")

    compiler_policy = policy or load_compiler_policy()
    provider = llm_provider or _build_required_provider(llm_settings)
    draft = provider.generate_spec_draft(
        prompt,
        build_generation_system_prompt(profile=profile, policy=compiler_policy),
    )
    return _spec_from_llm_draft(
        draft=draft,
        prompt=prompt,
        execution_mode=execution_mode,
        profile=profile,
        provider_name=provider.name,
        model_name=llm_settings.model if llm_settings else None,
        policy=compiler_policy,
    )


def spec_to_yaml(spec: Spec) -> str:
    return yaml.safe_dump(spec.to_dict(), sort_keys=False, allow_unicode=False)


def write_spec(spec: Spec, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(spec_to_yaml(spec))


def load_spec(path: str) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def summarize_spec(spec_data: Dict[str, object]) -> str:
    title = spec_data.get("title", "Untitled spec")
    objective = spec_data.get("objective", "")
    execution_mode = spec_data.get("execution_mode", "")
    actions = spec_data.get("actions", [])
    constraints = spec_data.get("constraints", [])
    metadata = spec_data.get("metadata") if isinstance(spec_data.get("metadata"), dict) else {}
    profile = metadata.get("profile") if isinstance(metadata.get("profile"), str) else ""

    lines = [
        f"Title: {title}",
        f"Objective: {objective}",
        f"Execution mode: {execution_mode}",
        f"Profile: {profile or 'not-set'}",
        f"Actions: {len(actions)}",
    ]
    if constraints:
        lines.append("Key constraints:")
        lines.extend(f"- {item}" for item in constraints[:3])
    return "\n".join(lines)


def summarize_spec_file(path: str) -> str:
    return summarize_spec(load_spec(path))


def _build_required_provider(llm_settings: Optional[LLMSettings]) -> LLMProvider:
    if not llm_settings:
        raise LLMError("An LLM provider is required to generate the spec.")
    return build_provider(llm_settings)


def _spec_from_llm_draft(
    draft: Dict[str, Any],
    prompt: str,
    execution_mode: str,
    profile: Optional[str],
    provider_name: str,
    model_name: Optional[str],
    policy: CompilerPolicy,
) -> Spec:
    context = Context.from_draft(draft.get("context"))
    hypotheses = _parse_hypotheses(draft.get("hypotheses"))
    actions = _parse_actions(draft.get("actions"), policy)
    metadata = _build_metadata(
        metadata=draft.get("metadata"),
        prompt=prompt,
        profile=profile,
        provider_name=provider_name,
        model_name=model_name,
        policy=policy,
    )

    try:
        spec = Spec(
            version=DEFAULT_VERSION,
            title=draft.get("title", ""),
            objective=draft.get("objective", ""),
            context=context,
            constraints=draft.get("constraints"),
            success_criteria=draft.get("success_criteria"),
            hypotheses=hypotheses,
            required_evidence=draft.get("required_evidence"),
            actions=actions,
            decision_rules=draft.get("decision_rules"),
            execution_mode=execution_mode,
            metadata=metadata,
        )
    except ValidationError as exc:
        raise LLMError(f"Spec validation failed: {exc}") from exc

    _ensure_min_items(spec, policy)
    _validate_spec_coherence(spec, policy)
    return spec


def _parse_hypotheses(value: Any) -> List[Hypothesis]:
    if not isinstance(value, list):
        return []
    seen_ids: set[str] = set()
    return [
        hypothesis
        for index, item in enumerate(value, start=1)
        for hypothesis in [Hypothesis.from_draft(item, index, seen_ids)]
        if hypothesis is not None
    ]


def _parse_actions(value: Any, policy: CompilerPolicy) -> List[Action]:
    if not isinstance(value, list):
        return []
    seen_ids: set[str] = set()
    actions = [
        action
        for index, item in enumerate(value, start=1)
        for action in [Action.from_draft(item, index, seen_ids)]
        if action is not None
    ]
    if policy.allowed_action_types:
        invalid = [action.type for action in actions if action.type not in policy.allowed_action_types]
        if invalid:
            raise LLMError(
                f"Action types are not allowed by compiler policy: {sorted(set(invalid))}. "
                f"Allowed: {sorted(policy.allowed_action_types)}"
            )
    return actions


def _build_metadata(
    metadata: Any,
    prompt: str,
    profile: Optional[str],
    provider_name: str,
    model_name: Optional[str],
    policy: CompilerPolicy,
) -> Dict[str, Any]:
    base_metadata = metadata if isinstance(metadata, dict) else {}
    final_metadata: Dict[str, Any] = {
        **base_metadata,
        "source_prompt": prompt,
        "generator": f"llm-{provider_name}",
        "model": model_name,
    }
    if profile:
        final_metadata["profile"] = profile

    scope_contract = final_metadata.get(policy.scope_contract_field)
    normalized_scope_contract = _normalize_scope_contract(scope_contract)
    if normalized_scope_contract:
        final_metadata[policy.scope_contract_field] = normalized_scope_contract
    elif policy.scope_contract_field in final_metadata:
        final_metadata.pop(policy.scope_contract_field)

    return final_metadata


def _normalize_scope_contract(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        return {}

    must_include = _dedupe(_coerce_list(value.get("must_include")))
    must_not_include = _dedupe(_coerce_list(value.get("must_not_include")))
    if not must_include and not must_not_include:
        return {}
    return {
        "must_include": must_include,
        "must_not_include": must_not_include,
    }


def _ensure_min_items(spec: Spec, policy: CompilerPolicy) -> None:
    section_values = {
        "assumptions": spec.context.assumptions,
        "constraints": spec.constraints,
        "success_criteria": spec.success_criteria,
        "hypotheses": spec.hypotheses,
        "required_evidence": spec.required_evidence,
        "actions": spec.actions,
        "decision_rules": spec.decision_rules,
    }
    for field, values in section_values.items():
        minimum = policy.min_items.get(field, 0)
        if len(values) < minimum:
            raise LLMError(f"Field '{field}' must have at least {minimum} item(s); received {len(values)}")


def _validate_spec_coherence(spec: Spec, policy: CompilerPolicy) -> None:
    errors: List[str] = []
    hypothesis_ids = {item.id for item in spec.hypotheses}
    linked_hypotheses: set[str] = set()

    for action in spec.actions:
        if policy.require_action_support_links and not action.supports:
            errors.append(f"action '{action.id}' is missing supports links")
            continue
        for target in action.supports:
            if target not in hypothesis_ids:
                errors.append(f"action '{action.id}' references unknown hypothesis '{target}'")
            else:
                linked_hypotheses.add(target)

    if policy.require_action_support_links:
        for hypothesis_id in sorted(hypothesis_ids - linked_hypotheses):
            errors.append(f"hypothesis '{hypothesis_id}' is not linked by any action")

    for key in sorted(policy.required_metadata_fields):
        value = spec.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"metadata.{key} must be a non-empty string")

    if errors:
        raise LLMError("Spec coherence validation failed: " + "; ".join(errors))


def _coerce_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        normalized = " ".join(item.strip().lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(item)
    return ordered
