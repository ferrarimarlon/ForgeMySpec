"""Project view for the guards: root, configuration, bundles, phases and path coverage.

Everything here is deterministic and cheap, because it runs on every Claude tool call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from .bundle import BundleLayout


STATE_DIR = Path(".forgemyspec") / "state"
# Bump when the gate record format changes: records from another schema count as "the gate never ran".
CACHE_SCHEMA = 2
CONFIG_FILE = Path(".forgemyspec") / "config.yaml"
SPEC_LOCK_NAME = "spec.lock"

DEFAULT_CONFIG: Dict[str, Any] = {
    "enforcement": "strict",
    # Free text that is not code: allowed, and listed in the box as unverified text.
    "allow_paths": ["**/*.md", "docs/**", "LICENSE*", "forgemyspec-board.yaml"],
    "code_extensions": [
        ".py", ".dfy", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".rb", ".php",
        ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".scala", ".sh", ".sql", ".lua", ".dart",
    ],
    "text_extensions": [".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"],
    # generated/ and _kernel/ hold code translated from proven Dafny; their source is already counted.
    "ignore_dirs": [".git", "node_modules", ".venv", "venv", "__pycache__", ".forgemyspec", "generated", "_kernel", "build", "dist"],
}

# Paths only the human changes: guard configuration, harness state, locks and generated code.
PROTECTED_GLOBS = [
    ".forgemyspec/**",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".githooks/**",
    ".github/workflows/forgemyspec.yml",
    "**/contract.lock",
    f"**/{SPEC_LOCK_NAME}",
    "**/generated/**",
]


def find_root(start: Optional[str] = None) -> Path:
    """Project root: CLAUDE_PROJECT_DIR, else the git top level, else the current directory."""
    env = os.getenv("CLAUDE_PROJECT_DIR")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    base = Path(start or os.getcwd()).resolve()
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(base), capture_output=True, text=True, timeout=5
        )
        if top.returncode == 0 and top.stdout.strip():
            return Path(top.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return base


def load_config(root: Path) -> Dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    path = root / CONFIG_FILE
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            config.update(loaded)
    return config


def rel(root: Path, path: Path) -> Optional[str]:
    """Path relative to the root with '/', or None when it is outside the project."""
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def matches(path: str, globs: Iterable[str]) -> bool:
    for pattern in globs:
        if fnmatch.fnmatchcase(path, pattern):
            return True
        # fnmatch does not treat "**/" as zero directories: "**/x.md" must also match "x.md".
        if pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:]):
            return True
    return False


def is_protected(path: str) -> bool:
    return matches(path, PROTECTED_GLOBS)


@dataclass
class Bundle:
    root: Path          # project root
    dir: Path           # bundle directory
    spec: Dict[str, Any]
    spec_error: str = ""

    @property
    def layout(self) -> BundleLayout:
        return BundleLayout.at(self.dir)

    @property
    def name(self) -> str:
        return rel(self.root, self.dir) or str(self.dir)

    @property
    def formal(self) -> bool:
        """Bundle with a Dafny contract (has contract.dfy or kind: dafny obligations)."""
        if self.layout.contract.exists():
            return True
        formal = self.spec.get("formal") if isinstance(self.spec.get("formal"), dict) else {}
        return any(isinstance(o, dict) and o.get("kind") == "dafny" for o in formal.get("obligations") or [])

    @property
    def scope(self) -> Dict[str, Any]:
        scope = self.spec.get("scope")
        return scope if isinstance(scope, dict) else {}

    @property
    def scope_paths(self) -> List[str]:
        return [p for p in self.scope.get("paths") or [] if isinstance(p, str) and p.strip()]

    @property
    def lock_path(self) -> Path:
        return self.layout.lock if self.formal else self.dir / SPEC_LOCK_NAME

    @property
    def locked(self) -> bool:
        return self.lock_path.exists()

    def lock_valid(self) -> bool:
        from .contract_lock import check_lock, check_spec_lock

        if not self.locked or self.spec_error:
            return False
        issues = check_lock(self.layout, self.spec) if self.formal else check_spec_lock(self.dir, self.spec)
        return not issues

    @property
    def phase(self) -> str:
        if self.spec_error:
            return "spec-invalid"
        if not self.locked:
            return "draft"
        return "locked" if self.lock_valid() else "lock-invalid"

    def covers(self, path: str) -> bool:
        """The path (relative to the root) is inside the bundle or in scope.paths."""
        own = rel(self.root, self.dir) or ""
        return path == own or path.startswith(own + "/") or matches(path, self.scope_paths)

    def input_files(self, config: Dict[str, Any]) -> List[Path]:
        """Files whose content decides whether the cached gate result still holds."""
        files = set()
        ignore = set(config["ignore_dirs"]) | {"generated"}
        for dirpath, dirnames, filenames in os.walk(self.dir):
            dirnames[:] = [d for d in dirnames if d not in ignore and not d.startswith(".")]
            for name in filenames:
                files.add(Path(dirpath) / name)
        for path in iter_project_files(self.root, config):
            r = rel(self.root, path)
            if r and matches(r, self.scope_paths):
                files.add(path)
        return sorted(files)

    def inputs_sha(self, config: Dict[str, Any]) -> str:
        digest = hashlib.sha256()
        for path in self.input_files(config):
            r = rel(self.root, path) or str(path)
            digest.update(r.encode("utf-8") + b"\0")
            try:
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            except OSError:
                digest.update(b"<unreadable>")
        return digest.hexdigest()


def discover_bundles(root: Path, config: Optional[Dict[str, Any]] = None) -> List[Bundle]:
    config = config or load_config(root)
    ignore = set(config["ignore_dirs"])
    bundles = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignore and not (d.startswith(".") and d != ".claude"))
        if "spec.yaml" in filenames:
            path = Path(dirpath)
            try:
                spec = yaml.safe_load((path / "spec.yaml").read_text(encoding="utf-8"))
                error = "" if isinstance(spec, dict) else "spec.yaml is not a YAML mapping"
            except (OSError, yaml.YAMLError) as exc:
                spec, error = {}, f"spec.yaml is unreadable: {str(exc).splitlines()[0]}"
            bundles.append(Bundle(root=root, dir=path.resolve(), spec=spec if isinstance(spec, dict) else {}, spec_error=error))
    return bundles


def owning_bundle(bundles: List[Bundle], path: str) -> Optional[Bundle]:
    """The innermost bundle whose directory contains the path."""
    best = None
    for bundle in bundles:
        own = rel(bundle.root, bundle.dir) or ""
        if path.startswith(own + "/") and (best is None or len(own) > len(rel(best.root, best.dir) or "")):
            best = bundle
    return best


def iter_project_files(root: Path, config: Dict[str, Any]) -> Iterable[Path]:
    """Project files: tracked ones plus new files git does not ignore; without git, a walk."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=str(root), capture_output=True, timeout=10,
        )
        if listed.returncode == 0:
            ignore = set(config["ignore_dirs"])
            for item in listed.stdout.decode("utf-8", "replace").split("\0"):
                if item and not any(part in ignore for part in item.split("/")[:-1]):
                    path = root / item
                    if path.is_file():
                        yield path
            return
    except (OSError, subprocess.TimeoutExpired):
        pass
    ignore = set(config["ignore_dirs"])
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for name in filenames:
            yield Path(dirpath) / name


# ---------------------------------------------------------------------------
# Harness state (.forgemyspec/state): gate cache, ledger, turn snapshots
# ---------------------------------------------------------------------------


def state_dir(root: Path) -> Path:
    path = root / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bundle_key(bundle: Bundle) -> str:
    return hashlib.sha256(bundle.name.encode("utf-8")).hexdigest()[:16]


def write_gate_cache(bundle: Bundle, config: Dict[str, Any], record: Dict[str, Any]) -> None:
    directory = state_dir(bundle.root) / "gate"
    directory.mkdir(exist_ok=True)
    payload = dict(record, bundle=bundle.name, inputs_sha=bundle.inputs_sha(config), schema=CACHE_SCHEMA)
    (directory / f"{_bundle_key(bundle)}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def read_gate_cache(bundle: Bundle) -> Optional[Dict[str, Any]]:
    path = bundle.root / STATE_DIR / "gate" / f"{_bundle_key(bundle)}.json"
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) and record.get("schema") == CACHE_SCHEMA else None


@dataclass
class GateStatus:
    bundle: Bundle
    cached: Optional[Dict[str, Any]]
    fresh: bool
    passed: bool
    failed_stages: List[str] = field(default_factory=list)


def gate_status(bundle: Bundle, config: Dict[str, Any]) -> GateStatus:
    cached = read_gate_cache(bundle)
    if not cached:
        return GateStatus(bundle, None, fresh=False, passed=False)
    fresh = cached.get("inputs_sha") == bundle.inputs_sha(config)
    failed = [s["name"] for s in cached.get("stages", []) if s.get("status") != "PASS"]
    return GateStatus(bundle, cached, fresh=fresh, passed=bool(cached.get("passed")), failed_stages=failed)


def append_ledger(root: Path, entry: Dict[str, Any]) -> None:
    try:
        with open(state_dir(root) / "ledger.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # the ledger feeds the audit; it must never take a guard down


def read_ledger(root: Path) -> List[Dict[str, Any]]:
    path = root / STATE_DIR / "ledger.jsonl"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
