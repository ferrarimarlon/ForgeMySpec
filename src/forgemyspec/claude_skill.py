from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any, Dict, List

import yaml

from . import messages as M
from .spec_io import load_spec


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
    command_path.write_text(render_implement_command(spec_data), encoding="utf-8")
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
    T = M.TEMPLATE_CLAUDE
    context = spec_data.get("context") if isinstance(spec_data.get("context"), dict) else {}
    sections = [
        T["title"], "", T["role_title"], T["role"], "", T["memory_title"],
        *[f"- {line}" for line in T["memory"]], "", T["snapshot_title"],
        f"- {T['spec_title'].format(title=_as_text(spec_data.get('title'), '-'))}",
        f"- {T['objective'].format(objective=_as_text(spec_data.get('objective'), ''))}",
    ]
    for title, key in (("guardrails_title", "constraints"), ("rules_title", "decision_rules"),
                       ("success_title", "success_criteria")):
        sections += ["", T[title]] + [f"- {item}" for item in _as_list(spec_data.get(key))]
    sections += ["", T["assumptions_title"]] + [f"- {item}" for item in _as_list(context.get("assumptions"))]
    sections += ["", T["protocol_title"], *T["protocol"], "", T["decisions_title"], T["decisions"],
                 "", T["pitfalls_title"], T["pitfalls"]]
    return "\n".join(sections).strip() + "\n"


def render_implement_command(spec_data: Dict[str, Any] | None = None) -> str:
    if isinstance(spec_data, dict) and isinstance(spec_data.get("formal"), dict):
        return M.TEMPLATE_COMMAND_FORMAL
    return M.TEMPLATE_COMMAND


def render_acceptance_checklist(spec_data: Dict[str, Any]) -> str:
    T = M.TEMPLATE_CHECKLIST
    lines = [
        T["title"], "", T["scope_title"], T["objective"].format(objective=_as_text(spec_data.get("objective"), "")),
        T["no_extras"], T["assumptions"], "", T["success_title"],
    ]
    lines += [f"- [ ] {item}" for item in _as_list(spec_data.get("success_criteria"))]
    lines += ["", T["evidence_title"]] + [f"- [ ] {item}" for item in _as_list(spec_data.get("required_evidence"))]
    lines += ["", T["rules_title"]] + [f"- [ ] {item}" for item in _as_list(spec_data.get("decision_rules"))]
    return "\n".join(lines).strip() + "\n"


def render_scope_eval_template(spec_data: Dict[str, Any]) -> str:
    metadata = spec_data.get("metadata") if isinstance(spec_data.get("metadata"), dict) else {}
    prompt = metadata.get("source_prompt") if isinstance(metadata.get("source_prompt"), str) else ""
    raw_contract = metadata.get("scope_contract") if isinstance(metadata, dict) else None
    scope_contract = _normalize_scope_contract(raw_contract)

    template = {
        "version": "0.1",
        "purpose": M.TEMPLATE_EVAL_PURPOSE,
        "source_prompt": prompt,
        "checks": {
            "must_include": scope_contract["must_include"],
        },
        "cases": [],
    }
    return yaml.safe_dump(template, sort_keys=False, allow_unicode=True)


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
