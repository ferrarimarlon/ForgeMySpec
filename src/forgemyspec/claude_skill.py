from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any, Dict, List

import yaml

from .generator import load_spec


@dataclass
class ClaudeSkillPackageResult:
    root: str
    spec_path: str
    memory_path: str
    command_path: str
    checklist_path: str
    eval_template_path: str


def package_claude_skill(spec_path: str, output_dir: str) -> ClaudeSkillPackageResult:
    spec_data = load_spec(spec_path)

    root = Path(output_dir).resolve()
    commands_dir = root / ".claude" / "commands"
    evals_dir = root / "evals"
    root.mkdir(parents=True, exist_ok=True)
    commands_dir.mkdir(parents=True, exist_ok=True)
    evals_dir.mkdir(parents=True, exist_ok=True)

    target_spec_path = root / "spec.yaml"
    source_spec_path = Path(spec_path).resolve()
    if source_spec_path != target_spec_path.resolve():
        shutil.copyfile(source_spec_path, target_spec_path)

    memory_path = root / "CLAUDE.md"
    command_path = commands_dir / "implement-from-spec.md"
    checklist_path = root / "acceptance-checklist.md"
    eval_template_path = evals_dir / "scope_drift_cases.yaml"

    memory_path.write_text(render_claude_memory(spec_data), encoding="utf-8")
    command_path.write_text(render_implement_command(), encoding="utf-8")
    checklist_path.write_text(render_acceptance_checklist(spec_data), encoding="utf-8")
    eval_template_path.write_text(render_scope_eval_template(spec_data), encoding="utf-8")

    return ClaudeSkillPackageResult(
        root=str(root),
        spec_path=str(target_spec_path),
        memory_path=str(memory_path),
        command_path=str(command_path),
        checklist_path=str(checklist_path),
        eval_template_path=str(eval_template_path),
    )


def render_claude_memory(spec_data: Dict[str, Any]) -> str:
    title = _as_text(spec_data.get("title"), "Untitled spec")
    objective = _as_text(spec_data.get("objective"), "")
    constraints = _as_list(spec_data.get("constraints"))
    decision_rules = _as_list(spec_data.get("decision_rules"))
    success_criteria = _as_list(spec_data.get("success_criteria"))
    assumptions = _as_list((spec_data.get("context") or {}).get("assumptions")) if isinstance(spec_data.get("context"), dict) else []

    sections = [
        "# CLAUDE.md",
        "",
        "## Role",
        "You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.",
        "",
        "## Persistent Memory Policy",
        "- This file is project memory and should persist across sessions.",
        "- Update only stable project knowledge (decisions, conventions, pitfalls).",
        "- Do not store ephemeral logs or temporary debugging notes here.",
        "",
        "## Current Spec Snapshot",
        f"- Title: {title}",
        f"- Objective: {objective}",
        "",
        "## Non-Negotiable Guardrails",
    ]
    sections.extend(f"- {item}" for item in constraints)

    sections.extend(
        [
            "",
            "## Decision Rules",
        ]
    )
    sections.extend(f"- {item}" for item in decision_rules)

    sections.extend(
        [
            "",
            "## Success Criteria",
        ]
    )
    sections.extend(f"- {item}" for item in success_criteria)

    sections.extend(
        [
            "",
            "## Assumptions",
        ]
    )
    sections.extend(f"- {item}" for item in assumptions)

    sections.extend(
        [
            "",
            "## Implementation Protocol",
            "1. Read `spec.yaml` first and implement only traceable scope.",
            "2. If details are missing, document explicit assumptions before coding.",
            "3. Do not add features, frameworks, or layers outside the spec objective.",
            "4. Verify all success criteria with concrete evidence (tests, commands, outputs).",
            "5. Report residual risks and unresolved assumptions in the final summary.",
            "",
            "## Decision Log",
            "- (record stable architecture or policy decisions here)",
            "",
            "## Known Pitfalls",
            "- (record recurring implementation failure modes here)",
        ]
    )

    return "\n".join(sections).strip() + "\n"


def render_implement_command() -> str:
    return (
        "Implement strictly from `./spec.yaml` and `./CLAUDE.md`.\n\n"
        "Execution steps:\n"
        "1. Parse objective, constraints, success criteria, decision rules, and actions from spec.\n"
        "2. Produce a short implementation plan mapped to action IDs.\n"
        "3. Implement only in-scope changes. Do not add unrequested features.\n"
        "4. Run validations/tests to satisfy success criteria.\n"
        "5. Return a final report with: changed files, evidence, assumptions made, and residual risks.\n"
    )


def render_acceptance_checklist(spec_data: Dict[str, Any]) -> str:
    objective = _as_text(spec_data.get("objective"), "")
    success_criteria = _as_list(spec_data.get("success_criteria"))
    required_evidence = _as_list(spec_data.get("required_evidence"))
    decision_rules = _as_list(spec_data.get("decision_rules"))

    lines = [
        "# Acceptance Checklist",
        "",
        "## Scope",
        f"- [ ] Objective implemented exactly: {objective}",
        "- [ ] No unrequested features were introduced",
        "- [ ] All assumptions are explicit and justified",
        "",
        "## Success Criteria",
    ]
    lines.extend(f"- [ ] {item}" for item in success_criteria)

    lines.extend(
        [
            "",
            "## Required Evidence",
        ]
    )
    lines.extend(f"- [ ] {item}" for item in required_evidence)

    lines.extend(
        [
            "",
            "## Decision Rules Compliance",
        ]
    )
    lines.extend(f"- [ ] {item}" for item in decision_rules)

    return "\n".join(lines).strip() + "\n"


def render_scope_eval_template(spec_data: Dict[str, Any]) -> str:
    metadata = spec_data.get("metadata") if isinstance(spec_data.get("metadata"), dict) else {}
    prompt = metadata.get("source_prompt") if isinstance(metadata.get("source_prompt"), str) else ""
    raw_contract = metadata.get("scope_contract") if isinstance(metadata, dict) else None
    scope_contract = _normalize_scope_contract(raw_contract)

    template = {
        "version": "0.1",
        "purpose": "Manual eval seeds to detect scope drift in Claude implementations",
        "source_prompt": prompt,
        "checks": {
            "must_include": scope_contract["must_include"],
        },
        "cases": [],
    }
    return yaml.safe_dump(template, sort_keys=False, allow_unicode=False)


def _as_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _as_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_scope_contract(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        return {"must_include": []}

    return {
        "must_include": _as_list(value.get("must_include")),
    }
