from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

from .bundle import BundleLayout
from .linting import LintIssue


# ---------------------------------------------------------------------------
# Source scanning
# ---------------------------------------------------------------------------


def strip_comments_and_strings(text: str) -> str:
    """Blank out comments, strings and char literals, keeping offsets and newlines intact."""
    out = list(text)
    i, n = 0, len(text)

    def blank(start: int, end: int) -> None:
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            end = text.find("\n", i)
            end = n if end == -1 else end
            blank(i, end)
            i = end
        elif ch == "/" and nxt == "*":
            # Dafny block comments nest.
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            blank(i, j)
            i = j
        elif ch == "@" and nxt == '"':
            # Verbatim string: "" is an escaped quote.
            j = i + 2
            while j < n:
                if text[j] == '"' and j + 1 < n and text[j + 1] == '"':
                    j += 2
                elif text[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            blank(i, j)
            i = j
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            blank(i, j + 1)
            i = j + 1
        elif ch == "'" and _is_char_literal(text, i):
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            blank(i, j + 1)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _is_char_literal(text: str, i: int) -> bool:
    # Primes are legal inside Dafny identifiers (x'), so a quote right after an
    # identifier character is not a char literal.
    prev = text[i - 1] if i > 0 else ""
    if prev.isalnum() or prev in "_'?":
        return False
    return re.match(r"'(\\.|[^'\\])'", text[i:]) is not None


TOKEN_PATTERN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_'?]*"
    r"|\d[\d_]*(?:\.\d+)?"
    r"|<==>|==>|<==|=>|::|:=|:\||==|!=|<=|>=|&&|\|\||!!|->|<-|\.\."
    r"|\S"
)

_CONTAINER_KEYWORDS = {"class", "trait", "datatype", "codatatype", "newtype", "type", "iterator"}
_MEMBER_KEYWORDS = {"method", "function", "predicate", "lemma", "constructor"}
_DECL_KEYWORDS = _CONTAINER_KEYWORDS | _MEMBER_KEYWORDS | {"module", "import", "const", "var"}
# A `{` after one of these starts an expression (set display or map), not a body.
_OPERAND_EXPECTING = {
    "requires", "ensures", "reads", "modifies", "decreases", "invariant",
    "in", "then", "else", "if", "returns", "yields", "assert", "old", "fresh",
}


@dataclass
class Member:
    kind: str
    name: str
    line: int
    container: str
    attributes: List[str] = field(default_factory=list)
    has_body: bool = False
    ensures_count: int = 0
    body_start: int = -1
    body_end: int = -1


@dataclass
class Module:
    name: str
    line: int
    abstract: bool
    refines: Optional[str]


@dataclass
class DafnyOutline:
    modules: List[Module]
    members: List[Member]


def outline(text: str) -> DafnyOutline:
    code = strip_comments_and_strings(text)
    tokens = [(m.group(0), m.start()) for m in TOKEN_PATTERN.finditer(code)]
    line_starts = [0] + [i + 1 for i, ch in enumerate(code) if ch == "\n"]

    def line_of(offset: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    modules: List[Module] = []
    members: List[Member] = []
    # Frames: (kind, name, member) with kind "module" | "type" | "body" | "group".
    stack: List[Tuple[str, str, Optional[Member]]] = []
    pending: Optional[Dict[str, Any]] = None
    member: Optional[Member] = None
    prev = ""
    abstract_next = False
    i = 0

    def container_level() -> bool:
        return not stack or stack[-1][0] in {"module", "type"}

    def skip_group(start: int) -> int:
        depth, j = 0, start
        while j < len(tokens):
            if tokens[j][0] == "{":
                depth += 1
            elif tokens[j][0] == "}":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return j

    while i < len(tokens):
        tok, offset = tokens[i]
        if container_level():
            if tok in _DECL_KEYWORDS or (tok == "}" and stack):
                member = None
            if tok == "abstract":
                abstract_next = True
            elif tok == "module" and i + 1 < len(tokens):
                name = tokens[i + 1][0]
                refines = None
                j = i + 2
                while j < len(tokens) and tokens[j][0] == ".":
                    name += "." + tokens[j + 1][0]
                    j += 2
                if j + 1 < len(tokens) and tokens[j][0] == "refines":
                    refines = tokens[j + 1][0]
                modules.append(Module(name=name, line=line_of(offset), abstract=abstract_next, refines=refines))
                pending = {"kind": "module", "name": name}
                abstract_next = False
            elif tok in _CONTAINER_KEYWORDS:
                name = tokens[i + 1][0] if i + 1 < len(tokens) else ""
                pending = {"kind": "type", "name": name}
            elif tok in _MEMBER_KEYWORDS:
                j = i + 1
                attributes: List[str] = []
                while j < len(tokens) and tokens[j][0] == "{" and j + 1 < len(tokens) and tokens[j + 1][0] == ":":
                    if j + 2 < len(tokens):
                        attributes.append(tokens[j + 2][0])
                    j = skip_group(j) + 1
                name = tokens[j][0] if j < len(tokens) else ""
                container = next((frame[1] for frame in reversed(stack) if frame[0] in {"module", "type"}), "")
                member = Member(kind=tok, name=name, line=line_of(offset), container=container, attributes=attributes)
                members.append(member)
                pending = None
                prev = name
                i = j + 1
                continue
            elif tok == "ensures" and member is not None:
                member.ensures_count += 1

            if tok == "{":
                is_attribute = i + 1 < len(tokens) and tokens[i + 1][0] == ":"
                if is_attribute:
                    i = skip_group(i) + 1
                    continue
                if pending is not None:
                    stack.append((pending["kind"], pending["name"], None))
                    pending = None
                elif member is not None and not member.has_body:
                    if _ends_expression(prev):
                        member.has_body = True
                        member.body_start = offset
                        stack.append(("body", member.name, member))
                    else:
                        i = skip_group(i) + 1
                        prev = "}"
                        continue
                else:
                    stack.append(("group", "", None))
            elif tok == "}" and stack:
                stack.pop()
        else:
            if tok == "{":
                stack.append(("group", "", None))
            elif tok == "}":
                frame = stack.pop()
                if frame[0] == "body" and frame[2] is not None:
                    frame[2].body_end = offset
                    member = None
        prev = tok
        i += 1

    return DafnyOutline(modules=modules, members=members)


def _ends_expression(token: str) -> bool:
    if not token:
        return False
    # `|` closes a cardinality expression such as `decreases |s|`; `{` never follows a bare `|` otherwise.
    if token in {")", "]", "}", ">", "|"}:
        return True
    if token in _OPERAND_EXPECTING:
        return False
    return token[0].isalnum() or token[0] == "_"


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

_BANNED_EVERYWHERE = [
    (re.compile(r"\bassume\b"), "`assume` statement"),
    (re.compile(r"\{\s*:\s*axiom\b"), "`{:axiom}` attribute"),
    (re.compile(r"\{\s*:\s*verify\s+false\s*\}"), "`{:verify false}` attribute"),
    (re.compile(r"\{\s*:\s*extern\b"), "`{:extern}` attribute"),
    (re.compile(r"\{\s*:\s*only\b"), "`{:only}` attribute"),
    (re.compile(r"\bdecreases\s+\*"), "`decreases *` (permits non-termination)"),
    (re.compile(r"\brequires\s+false\b"), "`requires false` (vacuous precondition)"),
    (re.compile(r"\bensures\s+true\b"), "`ensures true` (vacuous postcondition)"),
]
# `expect` is a runtime check the verifier treats as an assumption, so it is only legal in tests.
_BANNED_OUTSIDE_TESTS = [
    (re.compile(r"\bexpect\b"), "`expect` statement (verifier assumes it; use only in tests.dfy)"),
]

_TAG = re.compile(r"//\s*@obligation\s+([a-z0-9_,\s]+?)\s*$")
_CLAUSE_STARTS = {
    "requires", "ensures", "invariant", "method", "function", "predicate", "lemma",
    "ghost", "opaque", "twostate", "least", "greatest", "constructor",
}


def lint_bundle_dafny(layout: BundleLayout, spec_data: Dict[str, Any], require_impl: bool = True) -> List[LintIssue]:
    """Lint the bundle's Dafny files. With require_impl=False (lock time) impl.dfy may not exist yet."""
    issues: List[LintIssue] = []

    def add(code: str, message: str, location: str) -> None:
        issues.append(LintIssue(severity="error", code=code, message=message, location=location))

    formal = spec_data.get("formal") if isinstance(spec_data.get("formal"), dict) else {}
    module_name = formal.get("module") if isinstance(formal.get("module"), str) else ""
    obligations = [item for item in formal.get("obligations") or [] if isinstance(item, dict)]
    obligation_ids = {item.get("id") for item in obligations}
    dafny_obligations = [item.get("id") for item in obligations if item.get("kind") == "dafny"]

    required = layout.dafny_files if require_impl else [layout.contract, layout.tests]
    sources: Dict[str, str] = {}
    for path in layout.dafny_files:
        if path.exists():
            sources[path.name] = path.read_text(encoding="utf-8")
        elif path in required:
            add("LINT-DFY-000", f"Missing required file: {path.name}", path.name)
    if issues:
        return issues

    for name, text in sources.items():
        code = strip_comments_and_strings(text)
        rules = list(_BANNED_EVERYWHERE)
        if name != layout.tests.name:
            rules += _BANNED_OUTSIDE_TESTS
        for pattern, label in rules:
            for match in pattern.finditer(code):
                line = code.count("\n", 0, match.start()) + 1
                add("LINT-DFY-001", f"Banned construct: {label}", f"{name}:{line}")

    contract = outline(sources[layout.contract.name])
    tests = outline(sources[layout.tests.name])

    contract_modules = [m for m in contract.modules if m.name == module_name]
    if not contract_modules or not contract_modules[0].abstract:
        add("LINT-DFY-003", f"contract.dfy must declare `abstract module {module_name}`", layout.contract.name)
    if layout.impl.name in sources:
        impl = outline(sources[layout.impl.name])
        if not any(m.refines == module_name and not m.abstract for m in impl.modules):
            add("LINT-DFY-004", f"impl.dfy must declare a non-abstract `module ... refines {module_name}`", layout.impl.name)

    for member in contract.members:
        location = f"{layout.contract.name}:{member.line}"
        if member.kind == "method" and member.has_body:
            add("LINT-DFY-009", f"Contract method '{member.name}' has a body; implementations belong in impl.dfy", location)
        if member.kind == "method" and member.ensures_count == 0:
            add("LINT-DFY-011", f"Contract method '{member.name}' has no ensures clause, so it constrains nothing", location)
        if member.kind in {"function", "predicate"} and not member.has_body:
            add(
                "LINT-DFY-010",
                f"Contract {member.kind} '{member.name}' has no body; impl.dfy would get to define the specification",
                location,
            )

    contract_tags = _collect_tags(sources[layout.contract.name])
    tests_tags = _collect_tags(sources[layout.tests.name])
    test_methods = {m.line: m for m in tests.members if m.kind == "method" and "test" in m.attributes}

    for name, tags in ((layout.contract.name, contract_tags), (layout.tests.name, tests_tags)):
        for tag_line, ids, _next_line, _first in tags:
            for obligation_id in ids:
                if obligation_id not in obligation_ids:
                    add("LINT-DFY-007", f"Tag references unknown obligation id: {obligation_id}", f"{name}:{tag_line}")

    for obligation_id in dafny_obligations:
        in_contract = [
            tag for tag in contract_tags if obligation_id in tag[1] and tag[3] in _CLAUSE_STARTS
        ]
        if not in_contract:
            add(
                "LINT-DFY-005",
                f"Obligation '{obligation_id}' has no `// @obligation` tag directly above a contract clause or member",
                layout.contract.name,
            )
        in_tests = [tag for tag in tests_tags if obligation_id in tag[1] and tag[2] in test_methods]
        if not in_tests:
            add(
                "LINT-DFY-006",
                f"Obligation '{obligation_id}' has no `// @obligation` tag directly above a {{:test}} method",
                layout.tests.name,
            )

    return issues


def _collect_tags(text: str) -> List[Tuple[int, List[str], int, str]]:
    """Return (tag_line, ids, next_code_line, first_token_of_next_code_line) for each tag."""
    lines = text.splitlines()
    code_lines = strip_comments_and_strings(text).splitlines()
    tags = []
    for index, raw in enumerate(lines):
        match = _TAG.search(raw)
        if not match:
            continue
        ids = [part for part in re.split(r"[\s,]+", match.group(1)) if part]
        next_line, first = 0, ""
        for j in range(index + 1, len(code_lines)):
            stripped = code_lines[j].strip()
            if stripped:
                next_line = j + 1
                first = re.match(r"[A-Za-z_]+|\S", stripped).group(0)
                break
        tags.append((index + 1, ids, next_line, first))
    return tags
