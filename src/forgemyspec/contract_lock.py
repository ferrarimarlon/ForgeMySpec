from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List

import yaml

from .bundle import BundleLayout
from .linting import LintIssue


LOCK_VERSION = 1


def _sha256_file(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_formal(spec_data: Dict[str, Any]) -> str:
    canonical = json.dumps(spec_data.get("formal"), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_lock(layout: BundleLayout, spec_data: Dict[str, Any]) -> Dict[str, Any]:
    """What the user approves: the contract, the Dafny tests, and the obligation mapping."""
    return {
        "lock_version": LOCK_VERSION,
        "spec_version": str(spec_data.get("version", "")),
        "contract_sha256": _sha256_file(layout.contract),
        "tests_sha256": _sha256_file(layout.tests),
        "formal_sha256": _sha256_formal(spec_data),
    }


def write_lock(layout: BundleLayout, spec_data: Dict[str, Any]) -> Dict[str, Any]:
    lock = compute_lock(layout, spec_data)
    lock["locked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    layout.lock.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    return lock


def check_lock(layout: BundleLayout, spec_data: Dict[str, Any]) -> List[LintIssue]:
    issues: List[LintIssue] = []

    def add(code: str, message: str) -> None:
        issues.append(LintIssue(severity="error", code=code, message=message, location=layout.lock.name))

    if not layout.lock.exists():
        add("LOCK-001", "contract.lock is missing; the contract has not been approved and locked")
        return issues
    for path in (layout.contract, layout.tests):
        if not path.exists():
            add("LOCK-001", f"{path.name} is missing, so the lock cannot be checked")
    if issues:
        return issues

    try:
        recorded = yaml.safe_load(layout.lock.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        recorded = None
    if not isinstance(recorded, dict):
        add("LOCK-002", "contract.lock is not a valid YAML mapping")
        return issues

    current = compute_lock(layout, spec_data)
    labels = {
        "lock_version": "lock format version",
        "spec_version": "spec version",
        "contract_sha256": "contract.dfy",
        "tests_sha256": "tests.dfy",
        "formal_sha256": "spec.yaml formal section",
    }
    for key, label in labels.items():
        if str(recorded.get(key)) != str(current[key]):
            add("LOCK-003", f"{label} changed since the contract was approved; re-approve and run `lock` again")
    return issues
