from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from . import messages as M
from .bundle import BundleLayout
from .linting import LintIssue


# v2: the lock also covers the planted errors (planted/*.dfy).
LOCK_VERSION = 2
SPEC_LOCK_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sha256_formal(spec_data: Dict[str, Any]) -> str:
    canonical = json.dumps(spec_data.get("formal"), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_planted(layout: BundleLayout) -> str:
    digest = hashlib.sha256()
    for path in layout.planted_files:
        digest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def compute_lock(layout: BundleLayout, spec_data: Dict[str, Any]) -> Dict[str, Any]:
    """What the user approves: the contract, the Dafny tests, the planted errors and the obligation map."""
    return {
        "lock_version": LOCK_VERSION,
        "spec_version": str(spec_data.get("version", "")),
        "contract_sha256": _sha256_file(layout.contract),
        "tests_sha256": _sha256_file(layout.tests),
        "planted_sha256": _sha256_planted(layout),
        "formal_sha256": _sha256_formal(spec_data),
    }


def write_lock(layout: BundleLayout, spec_data: Dict[str, Any]) -> Dict[str, Any]:
    lock = compute_lock(layout, spec_data)
    lock["locked_at"] = _now()
    layout.lock.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    return lock


def _issue(code: str, message: str, location: str) -> LintIssue:
    return LintIssue(severity="error", code=code, message=message, location=location)


def check_lock(layout: BundleLayout, spec_data: Dict[str, Any]) -> List[LintIssue]:
    where = layout.lock.name
    if not layout.lock.exists():
        return [_issue("LOCK-001", M.LOCK_MISSING, where)]
    missing = [_issue("LOCK-001", M.LOCK_FILE_MISSING.format(file=p.name), where)
               for p in (layout.contract, layout.tests) if not p.exists()]
    if missing:
        return missing
    try:
        recorded = yaml.safe_load(layout.lock.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        recorded = None
    if not isinstance(recorded, dict):
        return [_issue("LOCK-002", M.LOCK_INVALID.format(file=where), where)]

    current = compute_lock(layout, spec_data)
    return [
        _issue("LOCK-003", M.LOCK_CHANGED.format(item=M.LOCK_ITEMS[key]), where)
        for key in current
        if str(recorded.get(key)) != str(current[key])
    ]


# ---------------------------------------------------------------------------
# Spec lock: approval of spec-only bundles (no Dafny contract)
# ---------------------------------------------------------------------------


def _spec_lock_path(bundle_dir) -> Path:
    return Path(bundle_dir) / "spec.lock"


def compute_spec_lock(bundle_dir, spec_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lock_version": SPEC_LOCK_VERSION,
        "spec_version": str(spec_data.get("version", "")),
        "spec_sha256": _sha256_file(Path(bundle_dir) / "spec.yaml"),
    }


def write_spec_lock(bundle_dir, spec_data: Dict[str, Any]) -> Dict[str, Any]:
    lock = compute_spec_lock(bundle_dir, spec_data)
    lock["approved_at"] = _now()
    _spec_lock_path(bundle_dir).write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    return lock


def check_spec_lock(bundle_dir, spec_data: Dict[str, Any]) -> List[LintIssue]:
    path = _spec_lock_path(bundle_dir)
    if not path.exists():
        return [_issue("LOCK-001", M.SPEC_LOCK_MISSING, path.name)]
    try:
        recorded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        recorded = None
    if not isinstance(recorded, dict):
        return [_issue("LOCK-002", M.LOCK_INVALID.format(file=path.name), path.name)]
    current = compute_spec_lock(bundle_dir, spec_data)
    if any(str(recorded.get(k)) != str(current[k]) for k in current):
        return [_issue("LOCK-003", M.SPEC_CHANGED_AFTER_APPROVAL, path.name)]
    return []


def approved_at(lock_path) -> str:
    """Approval time recorded in the lock, for the risk box."""
    try:
        data = yaml.safe_load(Path(lock_path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("approved_at") or data.get("locked_at") or "")
