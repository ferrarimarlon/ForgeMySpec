"""Deterministic harness entrypoint: `python -m forgemyspec <command>`. No LLM, no network."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import yaml

from .bundle import BundleLayout
from .claude_skill import package_claude_skill
from .contract_lock import write_lock
from .gate import FAIL, format_gate_report, run_gate, static_checks
from .linting import format_lint_report, lint_spec
from .nlp_policy import PolicyConfigError, load_compiler_policy
from .spec_io import load_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forgemyspec",
        description="ForgeMySpec harness: lint specs, lock approved Dafny contracts, and run the formal gate.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help="Lint a spec.yaml.")
    lint.add_argument("spec")
    lint.add_argument("--formal", action="store_true", help="Require the formal section (as the gate does).")

    package = sub.add_parser("package", help="Lint a spec.yaml and write the Claude bundle files next to it.")
    package.add_argument("spec")
    package.add_argument("--output-dir", help="Defaults to the spec's directory.")

    lock = sub.add_parser("lock", help="Record the user-approved contract.dfy, tests.dfy and formal section.")
    lock.add_argument("bundle")
    lock.add_argument("--check", action="store_true", help="Run the pre-lock checks without writing contract.lock.")

    gate = sub.add_parser("gate", help="Run every stage of the formal gate on a bundle.")
    gate.add_argument("bundle")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = load_compiler_policy()
    except PolicyConfigError as exc:
        print(f"Policy configuration error: {exc}", file=sys.stderr)
        return 2

    if args.command in {"lint", "package"}:
        try:
            spec_data = load_spec(args.spec)
        except (OSError, yaml.YAMLError) as exc:
            print(f"Cannot read {args.spec}: {str(exc).splitlines()[0]}", file=sys.stderr)
            return 1
        report = lint_spec(spec_data, policy=policy, require_formal=getattr(args, "formal", False))
        print(format_lint_report(report))
        failed = report.has_errors or report.score < policy.lint_min_passing_score
        if failed or args.command == "lint":
            return 1 if failed else 0
        output_dir = args.output_dir or str(Path(args.spec).resolve().parent)
        result = package_claude_skill(args.spec, output_dir)
        print(f"Bundle written to {result.root}")
        return 0

    if args.command == "lock":
        layout = BundleLayout.at(args.bundle)
        spec_data, stages = static_checks(layout, policy, require_impl=False)
        for stage in stages:
            print(f"  [{stage.status:<7}] {stage.name}")
            for detail in stage.details:
                print(f"              {detail}")
        if spec_data is None or any(stage.status == FAIL for stage in stages):
            print("Refusing to lock: fix the static checks first.", file=sys.stderr)
            return 1
        if args.check:
            print("Pre-lock checks passed; nothing was written.")
            return 0
        lock = write_lock(layout, spec_data)
        print(f"Locked {layout.lock} (spec version {lock['spec_version']})")
        return 0

    report = run_gate(args.bundle, policy=policy, progress=lambda name: print(f"  ... {name}", file=sys.stderr))
    print(format_gate_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
