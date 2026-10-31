from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class BundleLayout:
    """File layout of a formal bundle. Paths are fixed so the gate needs no configuration."""

    root: Path

    @classmethod
    def at(cls, root: str | Path) -> BundleLayout:
        return cls(Path(root).resolve())

    @property
    def spec(self) -> Path:
        return self.root / "spec.yaml"

    @property
    def contract(self) -> Path:
        return self.root / "contract.dfy"

    @property
    def impl(self) -> Path:
        return self.root / "impl.dfy"

    @property
    def tests(self) -> Path:
        return self.root / "tests.dfy"

    @property
    def lock(self) -> Path:
        return self.root / "contract.lock"

    @property
    def generated(self) -> Path:
        return self.root / "generated"

    @property
    def tests_py(self) -> Path:
        return self.root / "tests_py"

    @property
    def dafny_files(self) -> List[Path]:
        # Dafny skips verification of files reached only through `include`,
        # so every stage passes all three files explicitly.
        return [self.contract, self.impl, self.tests]

    @property
    def program_files(self) -> List[Path]:
        return [self.contract, self.impl]
