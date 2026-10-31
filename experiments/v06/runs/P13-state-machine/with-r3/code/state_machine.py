#!/usr/bin/env python3
"""State machine CLI: load a JSON definition, validate it, run events, print history.

Definition JSON:
  {"states": ["a", "b"], "initial": "a", "finals": ["b"],
   "transitions": [{"from": "a", "event": "go", "to": "b",
                    "guard": {"key": "n", "op": ">=", "value": 1}}]}

A guard is {"key", "op", "value"} or a non-empty list of them (all must hold).
Exit codes: 0 success, 1 rejected event, 2 invalid definition or bad input.
"""
import argparse
import json
import operator
import sys

OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda a, b: a in b,
}


class DefinitionError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def load_definition(path):
    """Read and parse a JSON file; raise DefinitionError on I/O or JSON errors."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise DefinitionError([f"cannot read {path}: {exc.strerror or exc}"])
    except ValueError as exc:
        raise DefinitionError([f"malformed JSON in {path}: {exc}"])


def _guard_problems(guard, where):
    items = guard if isinstance(guard, list) else [guard]
    if isinstance(guard, list) and not guard:
        return [f"{where}: guard list is empty"]
    problems = []
    for g in items:
        if not isinstance(g, dict) or not {"key", "op", "value"} <= set(g):
            problems.append(f"{where}: guard must be an object with key, op and value")
        elif not isinstance(g["key"], str):
            problems.append(f"{where}: guard key must be a string")
        elif g["op"] not in OPS:
            problems.append(f"{where}: unknown guard operator {g['op']!r}")
        elif g["op"] == "in" and not isinstance(g["value"], (list, str, dict)):
            problems.append(f"{where}: guard operator 'in' needs a list value")
    return problems


def validate(defn):
    """Return a list of problem strings; empty means the definition is valid."""
    if not isinstance(defn, dict):
        return ["definition must be a JSON object"]
    problems = []

    states = defn.get("states")
    if not isinstance(states, list) or not all(isinstance(s, str) for s in states):
        problems.append("states must be a list of strings")
        states = []
    elif len(set(states)) != len(states):
        problems.append("duplicate states declared")
    declared = set(states)

    initial = defn.get("initial")
    initial_ok = False
    if initial is None or initial == "":
        problems.append("missing initial state")
    elif not isinstance(initial, str):
        problems.append("initial must be a string")
    elif initial not in declared:
        problems.append(f"unknown state {initial!r} used as initial")
    else:
        initial_ok = True

    finals = defn.get("finals", [])
    if not isinstance(finals, list) or not all(isinstance(s, str) for s in finals):
        problems.append("finals must be a list of strings")
    else:
        for s in finals:
            if s not in declared:
                problems.append(f"unknown state {s!r} in finals")

    transitions = defn.get("transitions", [])
    edges = []
    if not isinstance(transitions, list):
        problems.append("transitions must be a list")
        transitions = []
    for i, t in enumerate(transitions):
        where = f"transitions[{i}]"
        if (not isinstance(t, dict)
                or not all(isinstance(t.get(k), str) for k in ("from", "event", "to"))):
            problems.append(f"{where}: needs string from, event and to")
            continue
        for role in ("from", "to"):
            if t[role] not in declared:
                problems.append(f"{where}: unknown state {t[role]!r} in {role}")
        if "guard" in t:
            problems.extend(_guard_problems(t["guard"], where))
        edges.append((t["from"], t["to"]))

    if initial_ok:
        seen, todo = {initial}, [initial]
        while todo:
            cur = todo.pop()
            for a, b in edges:
                if a == cur and b not in seen:
                    seen.add(b)
                    todo.append(b)
        for s in states:
            if s not in seen:
                problems.append(f"unreachable state {s!r}")
    return problems


def guard_holds(guard, context):
    """Evaluate a guard (object or list of objects) on the context; no eval."""
    if guard is None:
        return True
    items = guard if isinstance(guard, list) else [guard]
    for g in items:
        if g["key"] not in context:
            return False
        try:
            if not OPS[g["op"]](context[g["key"]], g["value"]):
                return False
        except TypeError:
            return False
    return True


def run_events(defn, events, context=None):
    """Apply events in order. Returns (history, state, rejected).

    history is a list of (from, event, to); rejected is the event that had no
    enabled transition (the run stops there) or None.
    """
    context = context or {}
    state = defn["initial"]
    history = []
    for event in events:
        for t in defn.get("transitions", []):
            if (t["from"] == state and t["event"] == event
                    and guard_holds(t.get("guard"), context)):
                history.append((state, event, t["to"]))
                state = t["to"]
                break
        else:
            return history, state, event
    return history, state, None


def format_history(history):
    if not history:
        return "history: (no transitions)"
    lines = ["history:"]
    for i, (a, e, b) in enumerate(history, 1):
        lines.append(f"  {i}. {a} --{e}--> {b}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run events against a JSON state machine.")
    ap.add_argument("definition", help="path to the JSON machine definition")
    ap.add_argument("events", nargs="*", help="events to apply in order")
    ap.add_argument("--context", default="{}", help="JSON object used by guards")
    args = ap.parse_args(argv)

    try:
        context = json.loads(args.context)
        if not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
    except ValueError as exc:
        print(f"error: bad --context: {exc}", file=sys.stderr)
        return 2
    try:
        defn = load_definition(args.definition)
        problems = validate(defn)
        if problems:
            raise DefinitionError(problems)
    except DefinitionError as exc:
        for p in exc.problems:
            print(f"error: {p}", file=sys.stderr)
        return 2

    history, state, rejected = run_events(defn, args.events, context)
    print(format_history(history))
    print(f"state: {state}" + (" (final)" if state in defn.get("finals", []) else ""))
    if rejected is not None:
        print(f"error: event {rejected!r} rejected in state {state!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
