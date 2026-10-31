from __future__ import annotations

from pathlib import Path
import shutil
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXAMPLE_BUNDLE = ROOT / "examples" / "budget-core"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def make_valid_spec_data() -> Dict[str, Any]:
    return {
        "version": "0.1",
        "title": "Build a parser CLI",
        "objective": "Create a deterministic parser CLI for arithmetic expressions.",
        "context": {
            "system": "Local repository with Python 3.9+ available.",
            "assumptions": ["The user wants a command-line interface."],
        },
        "constraints": [
            "Use only the standard library.",
            "Keep the implementation deterministic.",
        ],
        "success_criteria": [
            "The CLI parses valid expressions.",
            "Invalid expressions return a non-zero exit code.",
        ],
        "hypotheses": [
            {"id": "h1", "description": "A recursive descent parser is sufficient.", "confidence": 0.9},
            {"id": "h2", "description": "The CLI can report parse failures clearly.", "confidence": 0.8},
        ],
        "required_evidence": [
            "A command example for a valid expression.",
            "A command example for an invalid expression.",
        ],
        "actions": [
            {
                "id": "a1",
                "description": "Implement the parser module.",
                "type": "implement",
                "requires_confirmation": False,
                "supports": ["h1"],
            },
            {
                "id": "a2",
                "description": "Validate error reporting with invalid expression examples.",
                "type": "validate",
                "requires_confirmation": False,
                "supports": ["h2"],
            },
        ],
        "decision_rules": [
            "Stop and ask when a destructive change is required.",
            "Prefer the simplest parser that satisfies the requirements.",
        ],
        "execution_mode": "critical",
        "metadata": {
            "source_prompt": "build a parser cli",
            "generator": "claude-code-session",
            "scope_contract": {
                "must_include": ["parser cli", "argument parsing"],
            },
        },
    }


def copy_example_bundle(target: Path) -> Path:
    """Copy the budget-core example (sources only) so tests can inject faults safely."""
    destination = target / "budget-core"
    shutil.copytree(EXAMPLE_BUNDLE, destination, ignore=shutil.ignore_patterns("generated", "__pycache__"))
    return destination


KERNEL_BUNDLE = ROOT / "forgemyspec-bundle" / "kernel"


def make_project(target: Path) -> Path:
    """Temporary git project with three bundles: a locked formal one, an approved spec-only one and a draft spec-only one."""
    import subprocess
    import yaml as _yaml

    from forgemyspec.bundle import BundleLayout
    from forgemyspec.contract_lock import write_lock, write_spec_lock

    root = target / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    shutil.copytree(EXAMPLE_BUNDLE, root / "budget-core", ignore=shutil.ignore_patterns("generated", "__pycache__"))
    layout = BundleLayout.at(root / "budget-core")
    write_lock(layout, _yaml.safe_load(layout.spec.read_text(encoding="utf-8")))

    for name, paths, approve in (("app-spec", ["app/**"], True), ("draft-spec", ["draft/**"], False)):
        spec = make_valid_spec_data()
        spec["scope"] = {"paths": paths, "tests": f"{name}/tests_py"}
        spec["formal"] = {"module": "X", "obligations": [
            {"id": "o1", "kind": "boundary", "statement": "x", "hypotheses": ["h1", "h2"],
             "must_include": ["parser cli", "argument parsing"], "test": "test_x.T.test_x"}]}
        (root / name).mkdir()
        (root / name / "spec.yaml").write_text(_yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
        if approve:
            write_spec_lock(root / name, spec)
    (root / "app").mkdir()
    (root / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "README.md").write_text("# project\n", encoding="utf-8")
    return root
