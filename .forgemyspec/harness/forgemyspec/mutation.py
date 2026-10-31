from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import os
import re
import tempfile
from pathlib import Path
from typing import List, Tuple

from . import dafny_runner
from .bundle import BundleLayout
from .dafny_lint import TOKEN_PATTERN, outline, strip_comments_and_strings


_SWAPS = {
    "<": "<=", "<=": "<", ">": ">=", ">=": ">",
    "==": "!=", "!=": "==",
    "+": "-", "-": "+", "*": "+",
    "&&": "||", "||": "&&",
    "true": "false", "false": "true",
}
# Lines that state proof obligations rather than behavior; mutating them only tests the prover.
_ANNOTATION_STARTS = {"invariant", "decreases", "assert", "requires", "ensures", "modifies", "reads", "calc"}
_COLLECTION_TYPES = {"seq", "set", "iset", "multiset", "map", "imap", "array", "array2", "array3"}
_EQUIVALENT = re.compile(r"//\s*@equivalent-mutant:\s*(.*\S)?\s*$")

KILLED_VERIFY = "killed-verify"
KILLED_TEST = "killed-test"
SURVIVED = "survived"
TIMEOUT = "timeout"
INVALID = "invalid"


@dataclass
class Mutant:
    line: int
    column: int
    original: str
    replacement: str
    source: str
    status: str = ""
    detail: str = ""


@dataclass
class MutationReport:
    mutants: List[Mutant]
    suppressed: List[Tuple[int, str]] = field(default_factory=list)
    candidates: int = 0

    @property
    def killed(self) -> int:
        return sum(1 for m in self.mutants if m.status in {KILLED_VERIFY, KILLED_TEST})

    @property
    def scored(self) -> int:
        # Invalid mutants (did not parse or resolve) say nothing about the contract's strength.
        return sum(1 for m in self.mutants if m.status != INVALID)

    @property
    def kill_rate(self) -> float:
        return self.killed / self.scored if self.scored else 0.0

    @property
    def survivors(self) -> List[Mutant]:
        return [m for m in self.mutants if m.status in {SURVIVED, TIMEOUT}]


def generate_mutants(source: str, max_mutants: int) -> Tuple[List[Mutant], List[Tuple[int, str]], int]:
    code = strip_comments_and_strings(source)
    raw_lines = source.splitlines()
    code_lines = code.splitlines()
    spans = [(m.body_start, m.body_end) for m in outline(source).members if m.has_body and m.body_end > m.body_start]

    suppressed_lines = {}
    for index, raw in enumerate(raw_lines, start=1):
        match = _EQUIVALENT.search(raw)
        if match:
            suppressed_lines[index] = (match.group(1) or "").strip()

    tokens = [(m.group(0), m.start()) for m in TOKEN_PATTERN.finditer(code)]
    generic = _generic_brackets(tokens)
    candidates: List[Mutant] = []
    suppressed: List[Tuple[int, str]] = []
    for index, (tok, offset) in enumerate(tokens):
        if not any(start < offset < end for start, end in spans):
            continue
        if index in generic:
            continue
        replacement = _replacement(tok, tokens, index)
        if replacement is None:
            continue
        line = code.count("\n", 0, offset) + 1
        first_word = re.match(r"\s*([A-Za-z_]*)", code_lines[line - 1]).group(1)
        if first_word in _ANNOTATION_STARTS:
            continue
        if line in suppressed_lines:
            suppressed.append((line, suppressed_lines[line]))
            continue
        column = offset - (code.rfind("\n", 0, offset) + 1) + 1
        mutated = source[:offset] + replacement + source[offset + len(tok):]
        candidates.append(Mutant(line=line, column=column, original=tok, replacement=replacement, source=mutated))

    return _spread(candidates, max_mutants), sorted(set(suppressed)), len(candidates)


def _generic_brackets(tokens: List[Tuple[str, int]]) -> set:
    """Indices of `<` / `>` tokens that delimit type arguments (seq<int>, map<K, V>) rather than compare."""
    found: set = set()
    for index, (tok, _) in enumerate(tokens):
        prev = tokens[index - 1][0] if index else ""
        if tok != "<" or not (prev in _COLLECTION_TYPES or prev[:1].isupper()):
            continue
        depth = 0
        for j in range(index, min(len(tokens), index + 64)):
            if tokens[j][0] == "<":
                depth += 1
            elif tokens[j][0] == ">":
                depth -= 1
                if depth == 0:
                    found.update({index, j})
                    break
            elif tokens[j][0] in {";", "{", "}", ":=", "&&", "||"}:
                break
    return found


def _replacement(tok: str, tokens: List[Tuple[str, int]], index: int) -> str | None:
    prev = tokens[index - 1][0] if index else ""
    if tok == "-" and not (prev[:1].isalnum() or prev in {")", "]", "_"}):
        return None  # unary minus
    if tok in _SWAPS:
        return _SWAPS[tok]
    if re.fullmatch(r"\d+", tok):
        return str(int(tok) + 1)
    return None


def _spread(items: List[Mutant], cap: int) -> List[Mutant]:
    """Deterministically pick at most `cap` items spread evenly across the file."""
    if len(items) <= cap:
        return items
    if cap == 1:
        return [items[0]]
    step = (len(items) - 1) / (cap - 1)
    return [items[round(k * step)] for k in range(cap)]


def run_mutation(layout: BundleLayout, dafny: str, max_mutants: int, timeout: int) -> MutationReport:
    source = layout.impl.read_text(encoding="utf-8")
    mutants, suppressed, candidates = generate_mutants(source, max_mutants)
    workers = max(1, min(4, os.cpu_count() or 1))

    def evaluate(mutant: Mutant) -> None:
        with tempfile.TemporaryDirectory(prefix="forgemyspec-mutant-") as tmp:
            workdir = Path(tmp)
            dafny_runner.stage_copy(layout.dafny_files, workdir, {layout.impl.name: mutant.source})
            verified = dafny_runner.verify(dafny, workdir, layout.dafny_files, timeout, cores=1)
            if verified.timed_out:
                mutant.status, mutant.detail = TIMEOUT, "verify timed out"
                return
            if verified.returncode == dafny_runner.EXIT_VERIFICATION_FAILURE:
                mutant.status = KILLED_VERIFY
                return
            if verified.returncode != dafny_runner.EXIT_OK:
                mutant.status, mutant.detail = INVALID, f"dafny exit {verified.returncode}"
                return
            tested = dafny_runner.test(dafny, workdir, layout.dafny_files, timeout)
            if tested.timed_out:
                mutant.status, mutant.detail = TIMEOUT, "test timed out"
            elif tested.returncode == dafny_runner.EXIT_TEST_FAILURE:
                mutant.status = KILLED_TEST
            elif tested.returncode == dafny_runner.EXIT_OK:
                mutant.status = SURVIVED
            else:
                mutant.status, mutant.detail = INVALID, f"dafny test exit {tested.returncode}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(evaluate, mutants))

    return MutationReport(mutants=mutants, suppressed=suppressed, candidates=candidates)
