"""Deterministic harness entry point: `python -m forgemyspec <command>`. No LLM, no network."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import yaml

from . import messages as M
from .bundle import BundleLayout
from .claude_skill import package_claude_skill
from .contract_lock import write_lock, write_spec_lock
from .gate import FAIL, format_gate_report, run_gate, static_checks
from .linting import format_lint_report, lint_spec
from .nlp_policy import PolicyConfigError, load_compiler_policy
from .spec_io import load_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forgemyspec", description=M.CLI_DESCRIPTION)
    sub = parser.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help=M.CLI_HELP["lint"])
    lint.add_argument("spec")
    lint.add_argument("--formal", action="store_true", help=M.CLI_HELP["formal"])

    package = sub.add_parser("package", help=M.CLI_HELP["package"])
    package.add_argument("spec")
    package.add_argument("--output-dir", help=M.CLI_HELP["output-dir"])

    lock = sub.add_parser("lock", help=M.CLI_HELP["lock"])
    lock.add_argument("bundle")
    lock.add_argument("--check", action="store_true", help=M.CLI_HELP["check-lock"])

    approve = sub.add_parser("approve", help=M.CLI_HELP["approve"])
    approve.add_argument("bundle")
    approve.add_argument("--check", action="store_true", help=M.CLI_HELP["check-lock"])

    unlock = sub.add_parser("unlock", help=M.CLI_HELP["unlock"])
    unlock.add_argument("bundle")

    request = sub.add_parser("request-approval", help=M.CLI_HELP["request-approval"])
    request.add_argument("items", nargs="+", help=M.CLI_HELP["items"])

    gate = sub.add_parser("gate", help=M.CLI_HELP["gate"])
    gate.add_argument("bundle", nargs="?")
    gate.add_argument("--all", action="store_true", help=M.CLI_HELP["all"])
    gate.add_argument("--fast", action="store_true", help=M.CLI_HELP["fast"])

    hook = sub.add_parser("hook", help=M.CLI_HELP["hook"])
    hook.add_argument("event")

    board = sub.add_parser("board", help=M.CLI_HELP["board"])
    board.add_argument("detail", nargs="*", help=M.CLI_HELP["detail"])

    risk_cmd = sub.add_parser("risk", help=M.CLI_HELP["risk"])
    risk_cmd.add_argument("--json", action="store_true", help=M.CLI_HELP["json"])

    kernel = sub.add_parser("kernel", help=M.CLI_HELP["kernel"])
    kernel.add_argument("--check", action="store_true")
    kernel.add_argument("--bundle", default="forgemyspec-bundle/kernel")

    suspend = sub.add_parser("suspend", help=M.CLI_HELP["suspend"])
    suspend.add_argument("target", nargs="?", default=".")

    init = sub.add_parser("init", help=M.CLI_HELP["init"])
    init.add_argument("target", nargs="?", default=".")
    init.add_argument("--check", action="store_true", help=M.CLI_HELP["check-init"])
    init.add_argument("--python", default="python3", help=M.CLI_HELP["python"])
    return parser


def _print_stages(stages) -> None:
    for stage in stages:
        print(f"  [{M.STATUS[stage.status]:<7}] {M.STAGES.get(stage.name, stage.name)}")
        for detail in stage.details:
            print(f"              {detail}")


def _approval(action: str, target: str) -> Optional[dict]:
    """The user's approval for `action target`, or None after printing why it is missing.

    In the user's own terminal running the command is the approval. Anywhere else (Claude's Bash tool)
    the user must have typed the code of a matching request in the chat; TrustKernel.DecideApproval decides.
    """
    from . import approvals, project

    root = project.find_root()
    terminal = approvals.is_terminal()
    try:
        verdict = approvals.check(root, action, target, terminal)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(M.APPROVAL_UNREADABLE.format(item=f"{action}:{target}", error=exc), file=sys.stderr)
        return None
    if not verdict.approved:
        print(M.APPROVAL_REFUSED[verdict.reason].format(action=action, target=target, code=verdict.code), file=sys.stderr)
        return None
    approvals.consume(root, action, target, verdict)
    print(M.APPROVAL_TERMINAL if terminal else M.APPROVAL_USED.format(code=verdict.code))
    return {"approved_via": verdict.how, "approval_code": verdict.code} if verdict.code else {"approved_via": verdict.how}


def _request_approval(items: List[str]) -> int:
    from . import approvals, project

    parsed = []
    for item in items:
        action, sep, target = item.partition(":")
        if not sep or action not in approvals.ACTIONS:
            print(M.APPROVAL_BAD_ITEM.format(item=item, actions=", ".join(approvals.ACTIONS)), file=sys.stderr)
            return 1
        parsed.append((action, str(Path(target or ".").resolve())))
    root = project.find_root()
    try:
        code, records = approvals.request(root, parsed)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(M.APPROVAL_UNREADABLE.format(item=" ".join(items), error=exc), file=sys.stderr)
        return 1
    print(M.APPROVAL_REQUESTED.format(code=code))
    for r in records:
        print(M.APPROVAL_ITEM.format(action=r["action"], target=r["target"], sha=r["content_sha"][:12]))
    print(M.APPROVAL_ASK.format(code=code))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "request-approval":
        return _request_approval(args.items)

    if args.command == "hook":
        from .hooks import main as hook_main

        return hook_main(args.event)

    if args.command == "board":
        from . import board as board_view, project

        root = project.find_root()
        if args.detail[:1] == ["start"] and len(args.detail) == 2:
            board_view.start(root, args.detail[1])
            print(board_view.detail(root, args.detail[1]))
        else:
            print(board_view.detail(root, args.detail[0]) if args.detail else board_view.render(root))
        return 0

    if args.command == "risk":
        from . import project, risk

        if args.json:
            import json

            print(json.dumps(risk.panel(project.find_root()), ensure_ascii=False))
        else:
            print(risk.render(risk.build(project.find_root())))
        return 0

    if args.command == "kernel":
        from . import kernel

        if args.check:
            differing = kernel.check(Path(args.bundle))
            for item in differing:
                print(M.KERNEL_DIFFERS.format(item=item))
            print(M.KERNEL_MATCHES if not differing else M.KERNEL_DIVERGED)
            return 1 if differing else 0
        kernel.generate(Path(args.bundle))
        print(M.KERNEL_GENERATED.format(path=kernel.KERNEL_DIR))
        return 0

    if args.command == "suspend":
        from .install import suspend as suspend_guards

        target = str(Path(args.target).resolve())
        if _approval("suspend", target) is None:
            return 1
        return suspend_guards(Path(target))

    if args.command == "init":
        from .install import install

        if not args.check and _approval("init", str(Path(args.target).resolve())) is None:
            return 1
        return install(Path(args.target), check=args.check, python=args.python)

    try:
        policy = load_compiler_policy()
    except PolicyConfigError as exc:
        print(M.POLICY_ERROR.format(error=exc), file=sys.stderr)
        return 2

    if args.command in {"lint", "package"}:
        try:
            spec_data = load_spec(args.spec)
        except (OSError, yaml.YAMLError) as exc:
            print(M.CLI_FILE_UNREADABLE.format(file=args.spec, error=str(exc).splitlines()[0]), file=sys.stderr)
            return 1
        report = lint_spec(spec_data, policy=policy, require_formal=getattr(args, "formal", False))
        print(format_lint_report(report))
        failed = report.has_errors or report.score < policy.lint_min_passing_score
        if failed or args.command == "lint":
            return 1 if failed else 0
        output_dir = args.output_dir or str(Path(args.spec).resolve().parent)
        result = package_claude_skill(args.spec, output_dir)
        print(M.CLI_BUNDLE_WRITTEN.format(path=result.root))
        return 0

    if args.command in {"lock", "approve"}:
        layout = BundleLayout.at(args.bundle)
        if not layout.spec.exists():
            print(M.CLI_NOT_A_BUNDLE.format(path=args.bundle), file=sys.stderr)
            return 1
        if args.command == "approve" and layout.contract.exists():
            print(M.CLI_APPROVE_FORMAL.format(bundle=args.bundle), file=sys.stderr)
            return 1
        spec_data, stages = static_checks(layout, policy, require_impl=False)
        _print_stages(stages)
        if spec_data is None or any(stage.status == FAIL for stage in stages):
            print(M.CLI_LOCK_REFUSED, file=sys.stderr)
            return 1
        if args.check:
            print(M.CLI_LOCK_CHECKED)
            return 0
        approval = _approval(args.command, str(layout.root))
        if approval is None:
            return 1
        if args.command == "lock":
            lock = write_lock(layout, spec_data, approval)
            print(M.CLI_LOCK_WRITTEN.format(path=layout.lock, version=lock["spec_version"]))
        else:
            lock = write_spec_lock(layout.root, spec_data, approval)
            print(M.CLI_APPROVE_WRITTEN.format(path=layout.root / "spec.lock", version=lock["spec_version"]))
        return 0

    if args.command == "unlock":
        from . import project

        layout = BundleLayout.at(args.bundle)
        targets = [p for p in (layout.lock, layout.root / "spec.lock") if p.exists()]
        if not targets:
            print(M.CLI_UNLOCK_NO_LOCK.format(bundle=args.bundle), file=sys.stderr)
            return 1
        if _approval("unlock", str(layout.root)) is None:
            return 1
        keep = project.state_dir(project.find_root(str(layout.root))) / "removed-locks"
        keep.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for target in targets:
            shutil.copyfile(target, keep / f"{layout.root.name}-{target.name}-{stamp}")
            target.unlink()
            print(M.CLI_UNLOCK_DONE.format(path=target))
        return 0

    # gate
    if args.all or not args.bundle:
        from . import project

        root = project.find_root()
        targets = [b for b in project.discover_bundles(root) if b.locked]
        if not targets:
            print(M.CLI_NO_BUNDLES)
            return 0
        failed = False
        for bundle in targets:
            report = run_gate(str(bundle.dir), policy=policy, progress=lambda name: print(f"  … {name}", file=sys.stderr), fast=args.fast)
            print(format_gate_report(report))
            print()
            failed = failed or not report.passed
        return 1 if failed else 0
    report = run_gate(args.bundle, policy=policy, progress=lambda name: print(f"  … {name}", file=sys.stderr), fast=args.fast)
    print(format_gate_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
