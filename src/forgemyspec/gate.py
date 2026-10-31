from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from . import dafny_runner
from .bundle import BundleLayout
from .contract_lock import check_lock
from .dafny_lint import lint_bundle_dafny
from .linting import LintIssue, lint_spec
from .mutation import run_mutation
from .nlp_policy import CompilerPolicy, load_compiler_policy
from .spec_io import load_spec


PASS, FAIL, BLOCKED = "PASS", "FAIL", "BLOCKED"
GENERATED_NAME = "core"


@dataclass
class StageResult:
    name: str
    status: str
    details: List[str] = field(default_factory=list)


@dataclass
class GateReport:
    bundle: str
    stages: List[StageResult]

    @property
    def passed(self) -> bool:
        return all(stage.status == PASS for stage in self.stages)

    def stage(self, name: str) -> Optional[StageResult]:
        return next((stage for stage in self.stages if stage.name == name), None)


def _issue_lines(issues: List[LintIssue]) -> List[str]:
    return [f"[{issue.code}] {issue.location}: {issue.message}" for issue in issues]


def static_checks(
    layout: BundleLayout, policy: CompilerPolicy, require_impl: bool = True
) -> tuple[Optional[Dict[str, Any]], List[StageResult]]:
    """Checks that need no toolchain. `lock` reuses them (without impl.dfy) so an invalid contract is never locked."""
    stages: List[StageResult] = []
    if not layout.spec.exists():
        stages.append(StageResult("spec-lint", FAIL, [f"Missing {layout.spec}"]))
        return None, stages
    try:
        spec_data = load_spec(str(layout.spec))
    except yaml.YAMLError as exc:
        stages.append(StageResult("spec-lint", FAIL, [f"YAML parse error: {str(exc).splitlines()[0]}"]))
        return None, stages

    report = lint_spec(spec_data, policy=policy, require_formal=True)
    coverage = [issue for issue in report.issues if issue.code.startswith("LINT-FORMAL-")]
    other = [issue for issue in report.issues if not issue.code.startswith("LINT-FORMAL-")]
    other_errors = [issue for issue in other if issue.severity == "error"]
    spec_ok = not other_errors and report.score >= policy.lint_min_passing_score
    details = _issue_lines(other) + [f"score {report.score}/100 (minimum {policy.lint_min_passing_score})"]
    stages.append(StageResult("spec-lint", PASS if spec_ok else FAIL, details))
    stages.append(StageResult("obligation-coverage", FAIL if coverage else PASS, _issue_lines(coverage)))

    if not isinstance(spec_data, dict):
        return None, stages
    dafny_issues = lint_bundle_dafny(layout, spec_data, require_impl=require_impl)
    stages.append(StageResult("dafny-lint", FAIL if dafny_issues else PASS, _issue_lines(dafny_issues)))
    return spec_data, stages


def run_gate(bundle_dir: str, policy: Optional[CompilerPolicy] = None, progress: Callable[[str], None] = lambda _: None) -> GateReport:
    policy = policy or load_compiler_policy()
    layout = BundleLayout.at(bundle_dir)
    spec_data, stages = static_checks(layout, policy)

    if spec_data is not None:
        lock_issues = check_lock(layout, spec_data)
        stages.append(StageResult("contract-lock", FAIL if lock_issues else PASS, _issue_lines(lock_issues)))

    try:
        dafny, version = dafny_runner.require_dafny(policy.dafny_min_version)
        stages.append(StageResult("toolchain", PASS, [f"dafny {version} ({dafny})"]))
    except dafny_runner.ToolchainError as exc:
        dafny = ""
        stages.append(StageResult("toolchain", FAIL, [str(exc)]))

    dynamic = ["verify", "test", "audit", "translate", "python-boundary-tests", "mutation"]
    if any(stage.status != PASS for stage in stages):
        blocked_by = ", ".join(stage.name for stage in stages if stage.status != PASS)
        stages.extend(StageResult(name, BLOCKED, [f"blocked by: {blocked_by}"]) for name in dynamic)
        return GateReport(str(layout.root), stages)

    timeout = policy.dafny_timeout_seconds
    with tempfile.TemporaryDirectory(prefix="forgemyspec-gate-") as tmp:
        workdir = Path(tmp)
        dafny_runner.stage_copy(layout.dafny_files, workdir)

        progress("verify")
        result = dafny_runner.verify(dafny, workdir, layout.dafny_files, timeout)
        stages.append(StageResult("verify", PASS if result.ok else FAIL, result.tail()))

        if result.ok:
            progress("test")
            result = dafny_runner.test(dafny, workdir, layout.dafny_files, timeout)
            stages.append(StageResult("test", PASS if result.ok else FAIL, result.tail()))

            progress("audit")
            result, findings = dafny_runner.audit(dafny, workdir, layout.dafny_files, timeout)
            audit_ok = result.ok and findings == 0
            details = result.tail() if findings != 0 else [f"{findings} findings"]
            stages.append(StageResult("audit", PASS if audit_ok else FAIL, details))

            progress("translate")
            stages.append(_translate(dafny, workdir, layout, timeout))
        else:
            stages.extend(StageResult(name, BLOCKED, ["blocked by: verify"]) for name in dynamic[1:4])

    translated = stages[-1].name == "translate" and stages[-1].status == PASS
    if translated:
        progress("python-boundary-tests")
        stages.append(_python_tests(layout, spec_data))
    else:
        stages.append(StageResult("python-boundary-tests", BLOCKED, ["blocked by: translate"]))

    if all(stage.status == PASS for stage in stages):
        progress("mutation")
        stages.append(_mutation(layout, dafny, policy))
    else:
        stages.append(StageResult("mutation", BLOCKED, ["blocked by earlier failures"]))
    return GateReport(str(layout.root), stages)


def _translate(dafny: str, workdir: Path, layout: BundleLayout, timeout: int) -> StageResult:
    output = workdir / "translated" / GENERATED_NAME
    result = dafny_runner.translate_py(dafny, workdir, layout.program_files, output, timeout)
    produced = output.parent / f"{GENERATED_NAME}-py"
    if not result.ok or not produced.is_dir():
        return StageResult("translate", FAIL, result.tail())
    if layout.generated.exists():
        shutil.rmtree(layout.generated)
    layout.generated.mkdir(parents=True)
    shutil.copytree(produced, layout.generated / produced.name)
    return StageResult("translate", PASS, [f"wrote {layout.generated / produced.name}"])


_RUNNER = r"""
import json, sys, unittest
start = sys.argv[1]
loader = unittest.TestLoader()
suite = loader.discover(start_dir=start, top_level_dir=start)
def flatten(s):
    for item in s:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item
ids = [t.id() for t in flatten(suite)]
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
bad = sorted({t.id() for t, _ in result.failures + result.errors})
skipped = sorted({t.id() for t, _ in result.skipped})
print("@@FORGEMYSPEC@@" + json.dumps({"ids": ids, "failed": bad, "skipped": skipped}))
"""


def _python_tests(layout: BundleLayout, spec_data: Dict[str, Any]) -> StageResult:
    if not layout.tests_py.is_dir():
        return StageResult("python-boundary-tests", FAIL, ["tests_py/ is missing; the translated core needs Python tests"])
    generated = layout.generated / f"{GENERATED_NAME}-py"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(generated), str(layout.root)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", _RUNNER, str(layout.tests_py)],
        cwd=str(layout.root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    marker = [line for line in completed.stdout.splitlines() if line.startswith("@@FORGEMYSPEC@@")]
    if not marker:
        return StageResult("python-boundary-tests", FAIL, completed.stderr.strip().splitlines()[-15:])
    data = json.loads(marker[-1][len("@@FORGEMYSPEC@@"):])

    details = [f"{len(data['ids'])} tests, {len(data['failed'])} failed, {len(data['skipped'])} skipped"]
    ok = bool(data["ids"]) and not data["failed"]
    if not data["ids"]:
        details.append("no tests were discovered in tests_py/")
    details += [f"failed: {test_id}" for test_id in data["failed"]]

    obligations = (spec_data.get("formal") or {}).get("obligations") or []
    for item in obligations:
        if not isinstance(item, dict) or item.get("kind") != "boundary":
            continue
        test_id = item.get("test")
        if test_id not in data["ids"]:
            ok = False
            details.append(f"boundary obligation {item.get('id')}: test {test_id!r} was not found")
        elif test_id in data["skipped"]:
            ok = False
            details.append(f"boundary obligation {item.get('id')}: test {test_id!r} was skipped")
    if not ok:
        details += completed.stderr.strip().splitlines()[-15:]
    return StageResult("python-boundary-tests", PASS if ok else FAIL, details)


def _mutation(layout: BundleLayout, dafny: str, policy: CompilerPolicy) -> StageResult:
    report = run_mutation(layout, dafny, policy.max_mutants, policy.dafny_timeout_seconds)
    details = [
        f"{report.candidates} candidate mutants, {len(report.mutants)} run, "
        f"{report.killed}/{report.scored} killed ({report.kill_rate:.0%}), "
        f"{len(report.mutants) - report.scored} invalid; minimum {policy.mutation_min_kill_rate:.0%}"
    ]
    for mutant in report.survivors:
        details.append(
            f"{mutant.status}: impl.dfy:{mutant.line}:{mutant.column} `{mutant.original}` -> `{mutant.replacement}`"
            + (f" ({mutant.detail})" if mutant.detail else "")
        )
    unexplained = [line for line, reason in report.suppressed if not reason]
    for line, reason in report.suppressed:
        details.append(f"suppressed as equivalent: impl.dfy:{line} - {reason or 'NO REASON GIVEN'}")

    ok = report.scored > 0 and report.kill_rate >= policy.mutation_min_kill_rate and not unexplained
    if report.scored == 0:
        details.append("no valid mutants were generated, so the contract's strength is unmeasured")
    return StageResult("mutation", PASS if ok else FAIL, details)


def format_gate_report(report: GateReport) -> str:
    lines = [f"ForgeMySpec gate: {report.bundle}", ""]
    for stage in report.stages:
        lines.append(f"  [{stage.status:<7}] {stage.name}")
        lines.extend(f"              {detail}" for detail in stage.details)
    lines += ["", f"RESULT: {'PASS' if report.passed else 'FAIL'}"]
    return "\n".join(lines)
