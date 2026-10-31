"""Bridge to the trust kernel proven in Dafny (forgemyspec-bundle/kernel).

The rules live in Dafny and arrive here translated in `_kernel/`. This module only converts simple
Python types into the translated datatypes and back; it decides nothing on its own.
"""

from __future__ import annotations

import filecmp
import importlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

KERNEL_DIR = Path(__file__).resolve().parent / "_kernel"
GENERATED_FILES = ("KernelImpl.py", "module_.py", "_dafny", "System_")

_K = None
_D = None


def _load():
    global _K, _D
    if _K is None:
        path = str(KERNEL_DIR)
        if path not in sys.path:
            sys.path.insert(0, path)
        _D = importlib.import_module("_dafny")
        _K = importlib.import_module("KernelImpl")
    return _K, _D


def _name(value) -> str:
    """Status_Proven() -> 'Proven'."""
    return type(value).__name__.split("_", 1)[1]


def _text(seq) -> str:
    return "".join(seq)


def _seq_of_texts(items: Sequence[str]):
    _, d = _load()
    return d.SeqWithoutIsStrInference([d.Seq(i) for i in items])


# ---------------------------------------------------------------------------
# The four decisions
# ---------------------------------------------------------------------------

STATUS = {"Leaking": "leaking", "Fragile": "fragile", "Proven": "proven"}
OBLIGATION_REASON = {
    "ByProof": "proof", "ByBoundary": "boundary", "ByMutant": "mutant", "ByBlock": "blocked", "ByFailure": "failed",
}
PHASE = {"draft": "Draft", "locked": "Locked", "lock-invalid": "LockInvalid", "spec-invalid": "SpecInvalid"}
GATE = {"none": "NoGate", "stale": "Stale", "current": "Current"}
REQUIREMENT_REASON = {
    "NotApproved": "not-approved", "GateMissing": "no-gate", "GateStale": "stale",
    "Uncovered": "uncovered", "ByObligation": "obligation",
}
CATEGORIES = (
    "OutsideProject", "Protected", "Allowed", "BundleSpec", "BundleContract", "BundleImpl",
    "BundleDoc", "ScopeCovered", "NotCovered",
)


def classify_obligation(kind: str, failures: int, survivors: int, tests_ok: bool, blocked: bool) -> Tuple[str, str]:
    """kind: 'dafny' or 'boundary'. Returns (status, reason) in lower case."""
    k, _ = _load()
    kind_dafny = k.Kind_DafnyObligation() if kind == "dafny" else k.Kind_BoundaryObligation()
    s, r = k.default__.ClassifyObligation(kind_dafny, max(0, int(failures)), max(0, int(survivors)), bool(tests_ok), bool(blocked))
    return STATUS[_name(s)], OBLIGATION_REASON[_name(r)]


def requirement_status(phase: str, gate: str, coverage: List[str]) -> Tuple[str, str, Optional[int]]:
    """phase: a PHASE key; gate: 'none' | 'stale' | 'current'; coverage: statuses of the obligations covering it."""
    k, d = _load()
    inverse = {v: key for key, v in STATUS.items()}
    seq = d.SeqWithoutIsStrInference([getattr(k, f"Status_{inverse[s]}")() for s in coverage])
    s, r = k.default__.RequirementStatus(getattr(k, f"Phase_{PHASE[phase]}")(), getattr(k, f"GateState_{GATE[gate]}")(), seq)
    index = int(r.index) if r.is_ByObligation else None
    return STATUS[_name(s)], REQUIREMENT_REASON[_name(r)], index


def decide_edit(category: str, formal: bool, phase: str, changes_formal: bool, covering_approved: bool) -> Tuple[bool, Optional[str]]:
    """Returns (allow, reason); reason is the Dafny constructor name (e.g. 'RImplWithoutLock') when denying."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    k, _ = _load()
    decision = k.default__.DecideEdit(
        getattr(k, f"Category_{category}")(), bool(formal), getattr(k, f"Phase_{PHASE[phase]}")(),
        bool(changes_formal), bool(covering_approved),
    )
    return (True, None) if decision.is_Allow else (False, _name(decision.reason))


def coverage(
    hypotheses: Sequence[str], phrases: Sequence[str], refs_h: Sequence[Sequence[str]], refs_p: Sequence[Sequence[str]]
) -> Tuple[List[str], List[str]]:
    k, d = _load()
    mh, mp = k.default__.Coverage(
        _seq_of_texts(hypotheses), _seq_of_texts(phrases),
        d.SeqWithoutIsStrInference([_seq_of_texts(r) for r in refs_h]),
        d.SeqWithoutIsStrInference([_seq_of_texts(r) for r in refs_p]),
    )
    return [_text(x) for x in mh], [_text(x) for x in mp]


# ---------------------------------------------------------------------------
# Generating and checking _kernel/ (only in the ForgeMySpec repository)
# ---------------------------------------------------------------------------


def _translate(bundle: Path) -> Path:
    from . import dafny_runner
    from .bundle import BundleLayout

    layout = BundleLayout.at(bundle)
    dafny, _version = dafny_runner.require_dafny("4.0")
    workdir = Path(tempfile.mkdtemp(prefix="forgemyspec-kernel-"))
    dafny_runner.stage_copy(layout.program_files, workdir)
    result = dafny_runner.translate_py(dafny, workdir, layout.program_files, workdir / "out" / "core", 300)
    if not result.ok:
        raise RuntimeError("\n".join(result.tail()))
    return workdir / "out" / "core-py"


def generate(bundle: Path) -> None:
    source = _translate(bundle)
    if KERNEL_DIR.exists():
        shutil.rmtree(KERNEL_DIR)
    KERNEL_DIR.mkdir()
    for name in GENERATED_FILES:
        item = source / name
        if item.is_dir():
            shutil.copytree(item, KERNEL_DIR / name)
        else:
            shutil.copyfile(item, KERNEL_DIR / name)
    (KERNEL_DIR / "README.txt").write_text(
        "Generated by `python -m forgemyspec kernel` from forgemyspec-bundle/kernel.\n"
        "Do not edit by hand: CI compares this folder with a fresh translation.\n",
        encoding="utf-8",
    )


def check(bundle: Path) -> List[str]:
    """Lists the files in _kernel/ that differ from a fresh translation; empty when it matches."""
    source = _translate(bundle)
    differing: List[str] = []
    for name in GENERATED_FILES:
        a, b = source / name, KERNEL_DIR / name
        if not b.exists():
            differing.append(name)
        elif a.is_dir():
            stack = [filecmp.dircmp(a, b, ignore=["__pycache__"])]
            while stack:
                c = stack.pop()
                differing += [f"{name}/{x}" for x in c.left_only + c.right_only + c.diff_files]
                stack += list(c.subdirs.values())
        elif not filecmp.cmp(a, b, shallow=False):
            differing.append(name)
    return differing
