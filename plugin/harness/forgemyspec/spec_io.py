from __future__ import annotations

from typing import Any, Dict

import yaml


def spec_to_yaml(spec_data: Dict[str, Any]) -> str:
    return yaml.safe_dump(spec_data, sort_keys=False, allow_unicode=True)


def write_spec(spec_data: Dict[str, Any], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(spec_to_yaml(spec_data))


def load_spec(path: str) -> Any:
    """Load a spec file. Returns whatever YAML holds; lint_spec reports non-mapping results."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def summarize_spec(spec_data: Dict[str, Any]) -> str:
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
