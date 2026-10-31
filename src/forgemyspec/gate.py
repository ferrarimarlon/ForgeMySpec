from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from . import dafny_runner
from . import messages as M
from .bundle import BundleLayout
from .contract_lock import check_lock, check_spec_lock
from .dafny_lint import TARGET, _collect_tags, lint_bundle_dafny, outline
from .linting import LintIssue, lint_spec
from .mutation import run_mutation
from .nlp_policy import CompilerPolicy, load_compiler_policy
from .spec_io import load_spec


PASS, FAIL, BLOCKED = "PASS", "FAIL", "BLOCKED"
GENERATED_NAME = "core"
STATIC_STAGES = {"spec-lint", "obligation-coverage", "spec-lock"}


@dataclass
class StageResult:
    name: str
    status: str
    details: List[str] = field(default_factory=list)


@dataclass
class GateReport:
    bundle: str
    stages: List[StageResult]
    evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    strength: Dict[str, List[int]] = field(default_factory=dict)
    tier: str = "full"  # "fast": no mutation, no planted errors, only the obligations' tests

    @property
    def passed(self) -> bool:
        return all(stage.status == PASS for stage in self.stages)

    def stage(self, name: str) -> Optional[StageResult]:
        return next((stage for stage in self.stages if stage.name == name), None)

    def to_record(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stages": [{"name": s.name, "status": s.status, "details": s.details} for s in self.stages],
            "evidence": self.evidence,
            "strength": self.strength,
            "tier": self.tier,
        }


def _issue_lines(issues: List[LintIssue]) -> List[str]:
    return [f"[{issue.code}] {issue.location}: {issue.message}" for issue in issues]


def _tool_lines(lines: List[str]) -> List[str]:
    return [M.TOOL_PREFIX + line for line in lines]


# ---------------------------------------------------------------------------
# Per-obligation evidence
# ---------------------------------------------------------------------------


class _Evidence:
    """Collects, per obligation, what each stage proved or broke.

    Internal state per obligation: `fails` (stages that broke it), `survivors` (surviving mutants
    attributed to it), `tests_ok` (its tests ran and passed), `blocked` (the gate stopped earlier).
    """

    def __init__(self, spec_data: Dict[str, Any]):
        formal = spec_data.get("formal") if isinstance(spec_data.get("formal"), dict) else {}
        self.obligations = [o for o in formal.get("obligations") or [] if isinstance(o, dict) and o.get("id")]
        self.data: Dict[str, Dict[str, Any]] = {
            o["id"]: {
                "kind": o.get("kind"),
                "statement": o.get("statement", ""),
                "must_include": list(o.get("must_include") or []),
                "fails": [],
                "survivors": [],
                "tests_ok": False,
                "blocked": False,
            }
            for o in self.obligations
        }

    def ids(self, kind: Optional[str] = None) -> List[str]:
        return [i for i, d in self.data.items() if kind is None or d["kind"] == kind]

    def fail(self, obligation_id: str, stage: str, place: str = "") -> None:
        if obligation_id in self.data:
            entry = {"stage": stage, "place": place}
            if entry not in self.data[obligation_id]["fails"]:
                self.data[obligation_id]["fails"].append(entry)

    def finish(self) -> Dict[str, Dict[str, Any]]:
        """Classifies each obligation with the proven kernel (TrustKernel.ClassifyObligation)."""
        from . import kernel

        for d in self.data.values():
            d["status"], d["reason"] = kernel.classify_obligation(
                "dafny" if d["kind"] == "dafny" else "boundary",
                len(d["fails"]), len(d["survivors"]), d["tests_ok"], d["blocked"],
            )
        return self.data


def _obligations_by_contract_line(contract_text: str) -> Dict[int, List[str]]:
    """Contract clause/member line -> obligations whose tag sits directly above it."""
    return {next_line: ids for _tag, ids, next_line, _first in _collect_tags(contract_text) if next_line}


def _obligations_by_method(contract_text: str) -> Dict[str, List[str]]:
    """Contract method name -> obligations tagged on it (on the member or its clauses)."""
    members = sorted(outline(contract_text).members, key=lambda m: m.line)
    owners: Dict[str, List[str]] = {}
    for _tag, ids, next_line, _first in _collect_tags(contract_text):
        owner = None
        for member in members:
            if member.line <= next_line:
                owner = member
        if owner is not None:
            owners.setdefault(owner.name, [])
            owners[owner.name] += [i for i in ids if i not in owners[owner.name]]
    return owners


def _impl_method_at(impl_text: str, line: int) -> Optional[str]:
    for member in outline(impl_text).members:
        end = impl_text.count("\n", 0, member.body_end) + 1 if member.body_end > 0 else member.line
        if member.line <= line <= end:
            return member.name
    return None


_RELATED = re.compile(r"contract\.dfy\((\d+),\d+\): Related location")
_IMPL_ERROR = re.compile(r"impl\.dfy\((\d+),\d+\): Error")
_DAFNY_TEST = re.compile(r"^\S+?\.(\w+): (PASSED|FAILED)\s*$", re.MULTILINE)


def _attribute_verify(ev: _Evidence, output: str, layout: BundleLayout) -> None:
    contract = layout.contract.read_text(encoding="utf-8")
    impl = layout.impl.read_text(encoding="utf-8")
    by_line = _obligations_by_contract_line(contract)
    by_method = _obligations_by_method(contract)
    attributed = False
    for match in _RELATED.finditer(output):
        line = int(match.group(1))
        for obligation_id in by_line.get(line, []):
            ev.fail(obligation_id, "verify", f"contract.dfy:{line}")
            attributed = True
    for match in _IMPL_ERROR.finditer(output):
        line = int(match.group(1))
        method = _impl_method_at(impl, line)
        for obligation_id in by_method.get(method or "", []):
            if not ev.data[obligation_id]["fails"]:
                ev.fail(obligation_id, "verify", f"impl.dfy:{line}")
                attributed = True
    if not attributed:
        for obligation_id in ev.ids("dafny"):
            ev.fail(obligation_id, "verify")


def _attribute_dafny_tests(ev: _Evidence, output: str, layout: BundleLayout) -> None:
    tests_text = layout.tests.read_text(encoding="utf-8")
    test_lines = {m.name: m.line for m in outline(tests_text).members if "test" in m.attributes}
    tags_by_line = {next_line: ids for _t, ids, next_line, _f in _collect_tags(tests_text)}
    for name, status in _DAFNY_TEST.findall(output):
        for obligation_id in tags_by_line.get(test_lines.get(name, -1), []):
            if status == "FAILED":
                ev.fail(obligation_id, "test", f"tests.dfy:{name}")
            elif obligation_id in ev.data:
                ev.data[obligation_id]["tests_ok"] = True


# ---------------------------------------------------------------------------
# Static stages (no external tool)
# ---------------------------------------------------------------------------


def static_checks(
    layout: BundleLayout, policy: CompilerPolicy, require_impl: bool = True
) -> tuple[Optional[Dict[str, Any]], List[StageResult]]:
    """Checks that need no toolchain. `lock` reuses them (without impl.dfy) so an invalid contract is never locked."""
    stages: List[StageResult] = []
    if not layout.spec.exists():
        stages.append(StageResult("spec-lint", FAIL, [M.GATE_SPEC_MISSING.format(file=layout.spec)]))
        return None, stages
    try:
        spec_data = load_spec(str(layout.spec))
    except yaml.YAMLError as exc:
        stages.append(StageResult("spec-lint", FAIL, [M.GATE_YAML_INVALID.format(error=str(exc).splitlines()[0])]))
        return None, stages

    report = lint_spec(spec_data, policy=policy, require_formal=True)
    coverage = [issue for issue in report.issues if issue.code.startswith("LINT-FORMAL-")]
    other = [issue for issue in report.issues if not issue.code.startswith("LINT-FORMAL-")]
    spec_ok = not any(i.severity == "error" for i in other) and report.score >= policy.lint_min_passing_score
    details = _issue_lines(other) + [M.GATE_SCORE.format(score=report.score, minimum=policy.lint_min_passing_score)]
    stages.append(StageResult("spec-lint", PASS if spec_ok else FAIL, details))
    stages.append(StageResult("obligation-coverage", FAIL if coverage else PASS, _issue_lines(coverage)))

    if not isinstance(spec_data, dict):
        return None, stages
    if layout.contract.exists() or _has_dafny_obligations(spec_data):
        dafny_issues = lint_bundle_dafny(layout, spec_data, require_impl=require_impl)
        stages.append(StageResult("dafny-lint", FAIL if dafny_issues else PASS, _issue_lines(dafny_issues)))
    return spec_data, stages


def _has_dafny_obligations(spec_data: Dict[str, Any]) -> bool:
    formal = spec_data.get("formal") if isinstance(spec_data.get("formal"), dict) else {}
    return any(isinstance(o, dict) and o.get("kind") == "dafny" for o in formal.get("obligations") or [])


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def run_gate(
    bundle_dir: str,
    policy: Optional[CompilerPolicy] = None,
    progress: Callable[[str], None] = lambda _: None,
    write_cache: bool = True,
    fast: bool = False,
) -> GateReport:
    """The full gate, or with `fast` the in-session tier: mutation and planted errors are skipped and a spec-only
    bundle runs only the tests its obligations name. Pre-commit and CI run the full gate."""
    policy = policy or load_compiler_policy()
    layout = BundleLayout.at(bundle_dir)
    formal = layout.contract.exists() or (layout.spec.exists() and _spec_is_formal(layout))
    gate = _formal_gate if formal else _spec_only_gate
    report = gate(layout, policy, progress, fast)
    report.tier = "fast" if fast else "full"
    if write_cache:
        _write_cache(layout, report)
    return report


def _spec_is_formal(layout: BundleLayout) -> bool:
    try:
        spec = load_spec(str(layout.spec))
    except yaml.YAMLError:
        return False
    return isinstance(spec, dict) and _has_dafny_obligations(spec)


def _write_cache(layout: BundleLayout, report: GateReport) -> None:
    from . import project

    root = project.find_root(str(layout.root))
    if project.rel(root, layout.root) is None:
        return
    config = project.load_config(root)
    bundle = next((b for b in project.discover_bundles(root, config) if b.dir == layout.root), None)
    if bundle is None:
        return
    project.write_gate_cache(bundle, config, report.to_record())
    project.append_ledger(root, {"event": "gate", "bundle": bundle.name, "passed": report.passed,
                                 "ts": datetime.now(timezone.utc).isoformat()})


def _formal_gate(layout: BundleLayout, policy: CompilerPolicy, progress: Callable[[str], None], fast: bool = False) -> GateReport:
    spec_data, stages = static_checks(layout, policy)
    ev = _Evidence(spec_data or {})

    if spec_data is not None:
        lock_issues = check_lock(layout, spec_data)
        stages.append(StageResult("contract-lock", FAIL if lock_issues else PASS, _issue_lines(lock_issues)))

    try:
        dafny, version = dafny_runner.require_dafny(policy.dafny_min_version)
        stages.append(StageResult("toolchain", PASS, [M.GATE_TOOLCHAIN.format(version=version, path=dafny)]))
    except dafny_runner.ToolchainError as exc:
        dafny = ""
        stages.append(StageResult("toolchain", FAIL, [str(exc)]))

    dynamic = ["verify", "test", "audit", "translate", "python-boundary-tests", "mutation", "planted-errors"]
    if any(stage.status != PASS for stage in stages):
        blocked_by = ", ".join(M.STAGES.get(s.name, s.name) for s in stages if s.status != PASS)
        stages.extend(StageResult(n, BLOCKED, [M.GATE_BLOCKED_BY.format(stages=blocked_by)]) for n in dynamic)
        for obligation_id in ev.ids():
            ev.data[obligation_id]["blocked"] = True
        failed_static = [s.name for s in stages if s.status == FAIL]
        for obligation_id in ev.ids("dafny"):
            for name in failed_static:
                ev.fail(obligation_id, name)
        return GateReport(str(layout.root), stages, ev.finish())

    timeout = policy.dafny_timeout_seconds
    with tempfile.TemporaryDirectory(prefix="forgemyspec-gate-") as tmp:
        workdir = Path(tmp)
        dafny_runner.stage_copy(layout.dafny_files, workdir)

        progress("verify")
        result = dafny_runner.verify(dafny, workdir, layout.dafny_files, timeout)
        stages.append(StageResult("verify", PASS if result.ok else FAIL, _tool_lines(result.tail())))
        if not result.ok:
            _attribute_verify(ev, result.output, layout)
            stages.extend(StageResult(n, BLOCKED, [M.GATE_BLOCKED_BY.format(stages=M.STAGES["verify"])]) for n in dynamic[1:4])
        else:
            progress("test")
            result = dafny_runner.test(dafny, workdir, layout.dafny_files, timeout)
            stages.append(StageResult("test", PASS if result.ok else FAIL, _tool_lines(result.tail())))
            _attribute_dafny_tests(ev, result.output, layout)

            progress("audit")
            result, findings = dafny_runner.audit(dafny, workdir, layout.dafny_files, timeout)
            audit_ok = result.ok and findings == 0
            details = _tool_lines(result.tail()) if findings != 0 else [M.GATE_FINDINGS.format(n=findings)]
            stages.append(StageResult("audit", PASS if audit_ok else FAIL, details))
            if not audit_ok:
                for obligation_id in ev.ids("dafny"):
                    ev.fail(obligation_id, "audit")

            progress("translate")
            stages.append(_translate(dafny, workdir, layout, timeout))

    if stages[-1].name == "translate" and stages[-1].status == PASS:
        progress("python-boundary-tests")
        generated = layout.generated / f"{GENERATED_NAME}-py"
        stages.append(_python_tests(layout.tests_py, [generated, layout.root], layout.root, spec_data, ev))
    else:
        stages.append(StageResult("python-boundary-tests", BLOCKED, [M.GATE_BLOCKED_BY.format(stages=M.STAGES["translate"])]))

    strength: Dict[str, List[int]] = {}
    if fast:
        return GateReport(str(layout.root), stages, ev.finish(), strength)
    if all(stage.status == PASS for stage in stages):
        progress("mutation")
        stages.append(_mutation(layout, dafny, policy, ev, strength))
        progress("planted-errors")
        stages.append(_planted_errors(layout, dafny, policy, ev, strength))
    else:
        stages.append(StageResult("mutation", BLOCKED, [M.GATE_BLOCKED_EARLIER]))
        stages.append(StageResult("planted-errors", BLOCKED, [M.GATE_BLOCKED_EARLIER]))
        for obligation_id in ev.ids("dafny"):
            ev.data[obligation_id]["blocked"] = True
    return GateReport(str(layout.root), stages, ev.finish(), strength)


def _spec_only_gate(layout: BundleLayout, policy: CompilerPolicy, progress: Callable[[str], None], fast: bool = False) -> GateReport:
    from . import project

    spec_data, stages = static_checks(layout, policy)
    ev = _Evidence(spec_data or {})
    if spec_data is None:
        return GateReport(str(layout.root), stages, ev.finish())

    lock_issues = check_spec_lock(layout.root, spec_data)
    stages.append(StageResult("spec-lock", FAIL if lock_issues else PASS, _issue_lines(lock_issues)))

    root = project.find_root(str(layout.root))
    scope = spec_data.get("scope") if isinstance(spec_data.get("scope"), dict) else {}
    tests_dir = scope.get("tests")
    command = scope.get("verify_command")
    if not tests_dir and not command:
        stages.append(StageResult("python-boundary-tests", FAIL, [M.GATE_NO_VERIFICATION]))
    if tests_dir:
        progress("python-boundary-tests")
        pythonpath = [root / p for p in scope.get("pythonpath") or []] + [layout.root]
        only = None
        if fast:
            obligations = (spec_data.get("formal") or {}).get("obligations") or []
            only = [o["test"] for o in obligations if isinstance(o, dict) and o.get("test")]
        stages.append(_python_tests(root / tests_dir, pythonpath, root, spec_data, ev, only))
    if command and not fast:
        progress("verify-command")
        result = dafny_runner.run_command(["/bin/sh", "-c", command], cwd=root, timeout=max(600, policy.dafny_timeout_seconds))
        details = [M.GATE_COMMAND.format(command=command, code=result.returncode)] + _tool_lines(result.tail(8))
        stages.append(StageResult("verify-command", PASS if result.ok else FAIL, details))
        if not result.ok:
            for obligation_id in ev.ids():
                ev.fail(obligation_id, "verify-command")

    for s in stages:
        if s.status == FAIL and s.name in STATIC_STAGES:
            for obligation_id in ev.ids():
                ev.fail(obligation_id, s.name)
    return GateReport(str(layout.root), stages, ev.finish())


def _translate(dafny: str, workdir: Path, layout: BundleLayout, timeout: int) -> StageResult:
    output = workdir / "translated" / GENERATED_NAME
    result = dafny_runner.translate_py(dafny, workdir, layout.program_files, output, timeout)
    produced = output.parent / f"{GENERATED_NAME}-py"
    if not result.ok or not produced.is_dir():
        return StageResult("translate", FAIL, _tool_lines(result.tail()))
    if layout.generated.exists():
        shutil.rmtree(layout.generated)
    layout.generated.mkdir(parents=True)
    shutil.copytree(produced, layout.generated / produced.name)
    return StageResult("translate", PASS, [M.GATE_WROTE.format(path=layout.generated / produced.name)])


_RUNNER = r"""
import json, sys, unittest
start = sys.argv[1]
only = set(json.loads(sys.argv[2])) if len(sys.argv) > 2 else None
loader = unittest.TestLoader()
suite = loader.discover(start_dir=start, top_level_dir=start)
def flatten(s):
    for item in s:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item
tests = list(flatten(suite))
ids = [t.id() for t in tests]
if only is not None:
    suite = unittest.TestSuite([t for t in tests if t.id() in only])
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
bad = sorted({t.id() for t, _ in result.failures + result.errors})
skipped = sorted({t.id() for t, _ in result.skipped})
print("@@FORGEMYSPEC@@" + json.dumps({"ids": ids, "failed": bad, "skipped": skipped}))
"""


def _python_tests(
    tests_dir: Path, pythonpath: List[Path], cwd: Path, spec_data: Dict[str, Any], ev: _Evidence,
    only: Optional[List[str]] = None,
) -> StageResult:
    if not tests_dir.is_dir():
        for obligation_id in ev.ids("boundary"):
            ev.fail(obligation_id, "python-boundary-tests")
        return StageResult("python-boundary-tests", FAIL, [M.GATE_NO_TESTS_PY])
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in pythonpath)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", _RUNNER, str(tests_dir)] + ([json.dumps(only)] if only is not None else []),
        cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200,
    )
    marker = [line for line in completed.stdout.splitlines() if line.startswith("@@FORGEMYSPEC@@")]
    if not marker:
        for obligation_id in ev.ids("boundary"):
            ev.fail(obligation_id, "python-boundary-tests")
        return StageResult("python-boundary-tests", FAIL, _tool_lines(completed.stderr.strip().splitlines()[-15:]))
    data = json.loads(marker[-1][len("@@FORGEMYSPEC@@"):])

    details = [M.GATE_TESTS_SUMMARY.format(total=len(data["ids"]), failed=len(data["failed"]), skipped=len(data["skipped"]))]
    ok = bool(data["ids"]) and not data["failed"]
    if not data["ids"]:
        details.append(M.GATE_NO_TESTS.format(folder=tests_dir))
    details += [M.GATE_TEST_FAILED.format(id=test_id) for test_id in data["failed"]]

    for item in (spec_data.get("formal") or {}).get("obligations") or []:
        if not isinstance(item, dict) or item.get("kind") != "boundary":
            continue
        test_id = item.get("test")
        if test_id not in data["ids"]:
            ok = False
            details.append(M.GATE_BOUNDARY_MISSING.format(obligation=item.get("id"), test=test_id))
            ev.fail(item["id"], "python-boundary-tests", str(test_id))
        elif test_id in data["skipped"]:
            ok = False
            details.append(M.GATE_BOUNDARY_SKIPPED.format(obligation=item.get("id"), test=test_id))
            ev.fail(item["id"], "python-boundary-tests", str(test_id))
        elif test_id in data["failed"]:
            ev.fail(item["id"], "python-boundary-tests", str(test_id))
        elif item.get("id") in ev.data:
            ev.data[item["id"]]["tests_ok"] = True
    if not ok:
        details += _tool_lines(completed.stderr.strip().splitlines()[-15:])
    return StageResult("python-boundary-tests", PASS if ok else FAIL, details)


def _mutation(
    layout: BundleLayout, dafny: str, policy: CompilerPolicy, ev: _Evidence, strength: Dict[str, List[int]]
) -> StageResult:
    report = run_mutation(layout, dafny, policy.max_mutants, policy.dafny_timeout_seconds)
    strength["mutants"] = [report.killed, report.scored]
    details = [
        M.GATE_MUTATION_SUMMARY.format(
            candidates=report.candidates, run=len(report.mutants), killed=report.killed, valid=report.scored,
            rate=f"{report.kill_rate:.0%}", invalid=len(report.mutants) - report.scored,
            minimum=f"{policy.mutation_min_kill_rate:.0%}",
        )
    ]
    impl = layout.impl.read_text(encoding="utf-8")
    by_method = _obligations_by_method(layout.contract.read_text(encoding="utf-8"))
    for mutant in report.survivors:
        details.append(
            M.GATE_MUTANT_ALIVE.format(
                status=M.GATE_MUTANT_STATUS.get(mutant.status, mutant.status), line=mutant.line,
                column=mutant.column, original=mutant.original, replacement=mutant.replacement,
            )
        )
        method = _impl_method_at(impl, mutant.line)
        for obligation_id in by_method.get(method or "") or ev.ids("dafny"):
            if obligation_id in ev.data:
                ev.data[obligation_id]["survivors"].append(
                    {"place": f"impl.dfy:{mutant.line}", "original": mutant.original, "replacement": mutant.replacement}
                )
    unexplained = [line for line, reason in report.suppressed if not reason]
    for line, reason in report.suppressed:
        details.append(M.GATE_MUTANT_EQUIVALENT.format(line=line, reason=reason or M.GATE_MUTANT_NO_REASON))
    ok = report.scored > 0 and report.kill_rate >= policy.mutation_min_kill_rate and not unexplained
    if report.scored == 0:
        details.append(M.GATE_NO_MUTANTS)
    return StageResult("mutation", PASS if ok else FAIL, details)


def _planted_errors(
    layout: BundleLayout, dafny: str, policy: CompilerPolicy, ev: _Evidence, strength: Dict[str, List[int]]
) -> StageResult:
    """Each planted error is a plausible wrong impl.dfy; the contract and the tests must reject it."""
    planted = layout.planted_files
    timeout = policy.dafny_timeout_seconds
    rejected, details, ok = 0, [], True
    for error in planted:
        text = error.read_text(encoding="utf-8")
        match = TARGET.search(text)
        target = match.group(1) if match else "?"
        with tempfile.TemporaryDirectory(prefix="forgemyspec-planted-") as tmp:
            workdir = Path(tmp)
            dafny_runner.stage_copy(layout.dafny_files, workdir, {layout.impl.name: text})
            verified = dafny_runner.verify(dafny, workdir, layout.dafny_files, timeout, cores=1)
            if verified.returncode == dafny_runner.EXIT_VERIFICATION_FAILURE:
                # Rejected by the verifier: it only counts if the target obligation is the one that broke.
                probe = _Evidence({"formal": {"obligations": [{"id": i, "kind": d["kind"]} for i, d in ev.data.items()]}})
                _attribute_verify(probe, verified.output, BundleLayout.at(workdir))
                by = sorted(i for i, d in probe.data.items() if d["fails"])
                if target in by:
                    rejected += 1
                else:
                    ok = False
                    details.append(M.GATE_PLANTED_WRONG_REASON.format(file=error.name, target=target, by=", ".join(by) or "?"))
                continue
            if verified.returncode != dafny_runner.EXIT_OK:
                ok = False
                details.append(M.GATE_PLANTED_INVALID.format(file=error.name, code=verified.returncode))
                continue
            tested = dafny_runner.test(dafny, workdir, layout.dafny_files, timeout)
        if tested.returncode == dafny_runner.EXIT_TEST_FAILURE:
            rejected += 1
        elif tested.returncode == dafny_runner.EXIT_OK:
            ok = False
            details.append(M.GATE_PLANTED_SURVIVED.format(file=error.name, target=target))
            ev.fail(target, "planted-errors", f"planted/{error.name}")
        else:
            ok = False
            details.append(M.GATE_PLANTED_INVALID.format(file=error.name, code=tested.returncode))
    if len(planted) < policy.min_planted_errors:
        ok = False
        details.append(M.GATE_PLANTED_TOO_FEW.format(n=len(planted), minimum=policy.min_planted_errors))
    strength["planted"] = [rejected, len(planted)]
    summary = M.GATE_PLANTED_SUMMARY.format(rejected=rejected, total=len(planted), minimum=policy.min_planted_errors)
    return StageResult("planted-errors", PASS if ok else FAIL, [summary] + details)


def format_gate_report(report: GateReport) -> str:
    lines = [M.GATE_TITLE.format(bundle=report.bundle), ""]
    for stage in report.stages:
        lines.append(f"  [{M.STATUS[stage.status]:<7}] {M.STAGES.get(stage.name, stage.name)}")
        lines.extend(f"              {detail}" for detail in stage.details)
    lines += ["", M.GATE_RESULT.format(result=M.STATUS["PASS" if report.passed else "FAIL"])]
    return "\n".join(lines)
