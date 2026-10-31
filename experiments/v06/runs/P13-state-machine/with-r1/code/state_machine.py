#!/usr/bin/env python3
"""State machine CLI: load from JSON, validate, run events, print history.

Machine JSON:
  {"states": [...], "initial": "a", "final": ["c"],
   "transitions": [{"from": "a", "event": "go", "to": "b",
                    "guard": {"key": "n", "op": ">", "value": 3}}]}

Usage:
  state_machine.py validate MACHINE.json
  state_machine.py run MACHINE.json EVENT [EVENT ...] [--context JSON]

Exit codes: 0 ok, 1 invalid machine or rejected event, 2 usage / bad JSON.
"""
import argparse
import json
import operator
import sys

OPS = {
    "==": operator.eq, "!=": operator.ne, "<": operator.lt,
    "<=": operator.le, ">": operator.gt, ">=": operator.ge,
}


class LoadError(Exception):
    """Machine file unreadable or not valid JSON / wrong shape."""


def load_machine(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise LoadError(f"cannot read {path}: {e.strerror or e}")
    except ValueError as e:
        raise LoadError(f"malformed JSON in {path}: {e}")
    if not isinstance(data, dict):
        raise LoadError("machine definition must be a JSON object")
    return data


def validate(m):
    """Return a list of error strings (empty when the machine is valid)."""
    errors = []
    states = m.get("states")
    if not isinstance(states, list) or not all(isinstance(s, str) for s in states):
        return ["'states' must be a list of strings"]
    known = set(states)
    initial = m.get("initial")
    if not initial:
        errors.append("missing initial state")
    elif initial not in known:
        errors.append(f"unknown initial state: {initial}")
    finals = m.get("final", [])
    if not isinstance(finals, list):
        errors.append("'final' must be a list")
        finals = []
    for s in finals:
        if s not in known:
            errors.append(f"unknown final state: {s}")
    transitions = m.get("transitions", [])
    if not isinstance(transitions, list):
        return errors + ["'transitions' must be a list"]
    edges = {}
    for i, t in enumerate(transitions):
        if not isinstance(t, dict):
            errors.append(f"transition {i}: must be an object")
            continue
        for k in ("from", "event", "to"):
            if k not in t:
                errors.append(f"transition {i}: missing '{k}'")
        for k in ("from", "to"):
            if k in t and t[k] not in known:
                errors.append(f"unknown state in transition {i}: {t[k]}")
        g = t.get("guard")
        if g is not None:
            if (not isinstance(g, dict) or "key" not in g or "value" not in g
                    or g.get("op") not in OPS):
                errors.append(f"transition {i}: invalid guard (need key, op in "
                              f"{', '.join(OPS)}, value)")
        if t.get("from") in known and t.get("to") in known:
            edges.setdefault(t["from"], set()).add(t["to"])
    if initial in known:
        seen, stack = {initial}, [initial]
        while stack:
            for n in edges.get(stack.pop(), ()):
                if n not in seen:
                    seen.add(n)
                    stack.append(n)
        for s in states:
            if s not in seen:
                errors.append(f"unreachable state: {s}")
    return errors


def guard_holds(guard, context):
    if guard is None:
        return True
    key = guard["key"]
    if key not in context:
        return False
    try:
        return bool(OPS[guard["op"]](context[key], guard["value"]))
    except TypeError:
        return False


class Runner:
    def __init__(self, machine, context=None):
        self.machine = machine
        self.state = machine["initial"]
        self.context = context or {}
        self.history = []  # dicts: from, event, to, outcome

    def fire(self, event):
        """Attempt an event; record and return True if accepted."""
        src = self.state
        if src in self.machine.get("final", []):
            return self._record(src, event, src, "rejected (final state)")
        for t in self.machine.get("transitions", []):
            if (t["from"] == src and t["event"] == event
                    and guard_holds(t.get("guard"), self.context)):
                self.state = t["to"]
                return self._record(src, event, t["to"], "ok")
        return self._record(src, event, src, "rejected (no enabled transition)")

    def _record(self, src, event, dst, outcome):
        self.history.append({"from": src, "event": event, "to": dst, "outcome": outcome})
        return outcome == "ok"

    def run(self, events):
        return [self.fire(e) for e in events]


def format_history(history):
    return "\n".join(
        f"{i}. {h['from']} --{h['event']}--> {h['to']} [{h['outcome']}]"
        for i, h in enumerate(history, 1)
    )


def main(argv=None):
    p = argparse.ArgumentParser(prog="state_machine.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a machine definition")
    v.add_argument("machine")
    r = sub.add_parser("run", help="run events against a machine")
    r.add_argument("machine")
    r.add_argument("events", nargs="+")
    r.add_argument("--context", default="{}", help="JSON object used by guards")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    try:
        machine = load_machine(args.machine)
        context = None
        if args.cmd == "run":
            try:
                context = json.loads(args.context)
            except ValueError:
                raise LoadError("--context is not valid JSON")
            if not isinstance(context, dict):
                raise LoadError("--context must be a JSON object")
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errors = validate(machine)
    if errors:
        for e in errors:
            print(f"invalid: {e}")
        return 1
    if args.cmd == "validate":
        print("valid")
        return 0
    runner = Runner(machine, context)
    runner.run(args.events)
    print(format_history(runner.history))
    print(f"final state: {runner.state}")
    return 0 if all(h["outcome"] == "ok" for h in runner.history) else 1


if __name__ == "__main__":
    sys.exit(main())
