from __future__ import annotations

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

from . import messages as M


# Exit codes observed with Dafny 4.x.
EXIT_OK = 0
EXIT_DAFNY_ERROR = 2  # parse, resolution or type errors; also warnings without --allow-warnings
EXIT_TEST_FAILURE = 3
EXIT_VERIFICATION_FAILURE = 4

INSTALL_HINT = M.DAFNY_INSTALL


class ToolchainError(RuntimeError):
    pass


@dataclass
class CommandResult:
    args: List[str]
    returncode: int
    output: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == EXIT_OK and not self.timed_out

    def tail(self, lines: int = 15) -> List[str]:
        return [line for line in self.output.strip().splitlines() if line.strip()][-lines:]


def find_dafny() -> Optional[str]:
    override = os.getenv("FORGEMYSPEC_DAFNY")
    if override:
        return override if Path(override).exists() else None
    return shutil.which("dafny")


def dafny_version(dafny: str, timeout: int = 60) -> str:
    result = run_command([dafny, "--version"], cwd=None, timeout=timeout)
    match = re.search(r"\d+(?:\.\d+)+", result.output)
    if not result.ok or not match:
        raise ToolchainError(M.DAFNY_VERSION_UNREADABLE.format(dafny=dafny, output=result.output.strip()[:200]))
    return match.group(0)


def version_at_least(found: str, minimum: str) -> bool:
    def parts(value: str) -> List[int]:
        return [int(piece) for piece in value.split(".")]

    a, b = parts(found), parts(minimum)
    width = max(len(a), len(b))
    return a + [0] * (width - len(a)) >= b + [0] * (width - len(b))


def require_dafny(min_version: str) -> tuple[str, str]:
    dafny = find_dafny()
    if not dafny:
        raise ToolchainError(M.DAFNY_MISSING)
    version = dafny_version(dafny)
    if not version_at_least(version, min_version):
        raise ToolchainError(M.DAFNY_TOO_OLD.format(version=version, minimum=min_version))
    return dafny, version


def run_command(args: Sequence[str], cwd: Optional[Path], timeout: int, env: Optional[dict] = None) -> CommandResult:
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return CommandResult(list(args), returncode=-1, output=output + "\n" + M.TIMED_OUT.format(seconds=timeout), timed_out=True)
    return CommandResult(list(args), completed.returncode, completed.stdout)


def _names(files: Sequence[Path]) -> List[str]:
    return [path.name for path in files]


def verify(dafny: str, workdir: Path, files: Sequence[Path], timeout: int, cores: Optional[int] = None) -> CommandResult:
    args = [dafny, "verify", *_names(files)]
    if cores:
        args += ["--cores", str(cores)]
    return run_command(args, cwd=workdir, timeout=timeout)


def test(dafny: str, workdir: Path, files: Sequence[Path], timeout: int) -> CommandResult:
    # Tests run on the Python target: the same backend the core ships on.
    return run_command([dafny, "test", "--no-verify", "--target", "py", *_names(files)], cwd=workdir, timeout=timeout)


def audit(dafny: str, workdir: Path, files: Sequence[Path], timeout: int) -> tuple[CommandResult, int]:
    """Return the result and the number of findings. `dafny audit` exits 0 even when it has findings."""
    result = run_command([dafny, "audit", *_names(files)], cwd=workdir, timeout=timeout)
    match = re.search(r"completed with (\d+) findings?", result.output)
    findings = int(match.group(1)) if match else -1
    return result, findings


def translate_py(dafny: str, workdir: Path, files: Sequence[Path], output: Path, timeout: int) -> CommandResult:
    return run_command(
        [dafny, "translate", "py", "--no-verify", "--include-runtime", "--output", str(output), *_names(files)],
        cwd=workdir,
        timeout=timeout,
    )


def stage_copy(files: Sequence[Path], workdir: Path, replacements: Optional[dict] = None) -> None:
    """Copy bundle sources into a scratch directory so Dafny build output never lands in the bundle."""
    replacements = replacements or {}
    for path in files:
        target = workdir / path.name
        if path.name in replacements:
            target.write_text(replacements[path.name], encoding="utf-8")
        else:
            shutil.copyfile(path, target)
