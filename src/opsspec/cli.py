from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .branding import (
    render_assistant_line,
    render_banner,
    render_footer,
    render_help,
    render_shell_intro,
    render_user_prompt,
)
from .claude_skill import package_claude_skill
from .config import load_default_dotenvs
from .generator import build_spec, write_spec
from .linting import format_lint_report, lint_spec
from .llm import LLMError, LLMSettings
from .nlp_policy import CompilerPolicy, PolicyConfigError, load_compiler_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specforge",
        description="Simple spec builder: prompt in, validated skill bundle out.",
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Optional free-form task text (e.g., specforge \"build a parser cli\").",
    )
    parser.add_argument("--prompt", help="Free-form prompt.")
    parser.add_argument("--from-file", help="Input prompt file.")
    parser.add_argument(
        "--output-dir",
        default="specforge-skill",
        help="Output directory for generated spec and Claude bundle.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_default_dotenvs()
    argv = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        policy = load_compiler_policy()
    except PolicyConfigError as exc:
        raise SystemExit(f"Compiler policy configuration error: {exc}") from exc

    provider = _resolve_provider()
    llm_settings = LLMSettings(provider=provider)

    prompt = _read_prompt_from_args(args.prompt, args.from_file, args.task)
    if prompt is not None:
        return _run_pipeline(prompt, args.output_dir, llm_settings, provider, policy, interactive=False)

    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return _run_pipeline(piped, args.output_dir, llm_settings, provider, policy, interactive=False)
        raise SystemExit("No prompt received from stdin.")

    return _run_interactive_client(args.output_dir, llm_settings, provider, policy)


def _run_pipeline(
    prompt: str,
    output_dir_arg: str,
    llm_settings: LLMSettings,
    provider: str,
    policy: CompilerPolicy,
    interactive: bool,
) -> int:
    try:
        spec = build_spec(prompt, execution_mode="advisory", llm_settings=llm_settings, policy=policy)
    except LLMError as exc:
        if interactive:
            print(render_assistant_line(f"Failed with provider '{provider}': {exc}"))
            return 1
        raise SystemExit(f"Failed to generate spec with provider '{provider}': {exc}") from exc
    except PolicyConfigError as exc:
        if interactive:
            print(render_assistant_line(f"Compiler policy configuration error: {exc}"))
            return 1
        raise SystemExit(f"Compiler policy configuration error: {exc}") from exc

    output_dir = Path(output_dir_arg).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = output_dir / "spec.yaml"
    write_spec(spec, str(spec_path))

    try:
        report = lint_spec(spec.to_dict(), policy=policy)
    except PolicyConfigError as exc:
        if interactive:
            print(render_assistant_line(f"Compiler policy configuration error: {exc}"))
            return 1
        raise SystemExit(f"Compiler policy configuration error: {exc}") from exc

    lint_failed = report.has_errors or report.score < policy.lint_min_passing_score
    if lint_failed:
        if interactive:
            print(render_assistant_line(f"Spec generated at {spec_path}"))
            for line in format_lint_report(report).splitlines():
                print(render_assistant_line(line))
            print(
                render_assistant_line(
                    f"Packaging blocked due to lint failures (minimum score: {policy.lint_min_passing_score})."
                )
            )
            return 1
        print(f"Spec generated at {spec_path}")
        print(format_lint_report(report))
        print(f"Packaging blocked due to lint failures (minimum score: {policy.lint_min_passing_score}).")
        return 1

    result = package_claude_skill(str(spec_path), str(output_dir))
    if interactive:
        print(render_assistant_line(f"Spec generated at {spec_path}"))
        for line in format_lint_report(report).splitlines():
            print(render_assistant_line(line))
        print(render_assistant_line(f"Claude skill bundle written to {result.root}"))
        return 0

    print(f"Spec generated at {spec_path}")
    print(format_lint_report(report))
    print(f"Claude skill bundle written to {result.root}")
    print(f"- spec: {result.spec_path}")
    print(f"- memory: {result.memory_path}")
    print(f"- command: {result.command_path}")
    print(f"- checklist: {result.checklist_path}")
    print(f"- eval template: {result.eval_template_path}")
    return 0


def _run_interactive_client(
    output_dir: str,
    llm_settings: LLMSettings,
    provider: str,
    policy: CompilerPolicy,
) -> int:
    print(render_banner())
    print(render_shell_intro())
    print(render_footer())
    current_output_dir = output_dir
    while True:
        try:
            user_text = input(render_user_prompt()).strip()
        except EOFError:
            print()
            return 0
        if not user_text:
            continue
        if user_text in {"/quit", "/exit"}:
            return 0
        if user_text in {"/help", "help"}:
            print(render_help())
            continue
        chosen_output = _ask_output_dir(current_output_dir)
        current_output_dir = chosen_output
        _run_pipeline(user_text, chosen_output, llm_settings, provider, policy, interactive=True)


def _ask_output_dir(default_output_dir: str) -> str:
    try:
        typed = input(f"Output folder [{default_output_dir}]: ").strip()
    except EOFError:
        print()
        return default_output_dir
    return typed or default_output_dir


def _read_prompt_from_args(direct_prompt: str | None, file_path: str | None, task_parts: list[str] | None) -> str | None:
    if task_parts:
        joined = " ".join(part.strip() for part in task_parts if part.strip()).strip()
        if joined:
            return joined
    if direct_prompt:
        return direct_prompt
    if file_path:
        with open(file_path, "r", encoding="utf-8") as handle:
            return handle.read()
    return None


def _resolve_provider() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"

    raise SystemExit(
        "No provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
        "then run again."
    )


if __name__ == "__main__":
    sys.exit(main())
