from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def make_valid_draft() -> Dict[str, Any]:
    return {
        "title": "Build a parser CLI",
        "objective": "Create a deterministic parser CLI for arithmetic expressions.",
        "context": {
            "system": "Local repository with Python 3.9+ available.",
            "assumptions": [
                "The user wants a command-line interface.",
                "The user wants a command-line interface.",
            ],
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
            {"id": "Parser", "description": "A recursive descent parser is sufficient.", "confidence": 0.9},
            {"id": "Parser", "description": "Duplicate ids should be normalized.", "confidence": 0.6},
        ],
        "required_evidence": [
            "A command example for a valid expression.",
            "A command example for an invalid expression.",
        ],
        "actions": [
            {
                "id": "Implement Parser",
                "description": "Implement the parser module.",
                "type": "Implement",
                "requires_confirmation": False,
                "supports": ["Parser"],
            },
            {
                "id": "Validate CLI",
                "description": "Validate the CLI behavior with examples.",
                "type": "Validate",
                "requires_confirmation": False,
                "supports": ["Parser_2"],
            },
        ],
        "decision_rules": [
            "Stop and ask when a destructive change is required.",
            "Prefer the simplest parser that satisfies the requirements.",
        ],
        "metadata": {
            "scope_contract": {
                "must_include": ["parser cli", "argument parsing"],
                "must_not_include": ["web ui", "database"],
            }
        },
    }


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
            "generator": "llm-openai",
            "scope_contract": {
                "must_include": ["parser cli", "argument parsing"],
            },
        },
    }
