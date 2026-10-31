#!/usr/bin/env python3
"""State machine CLI.

Machine definition (JSON):
{
  "initial": "idle",
  "states": ["idle", "running", "done"],
  "final": ["done"],
  "transitions": [
    {"from": "idle", "event": "start", "to": "running"},
    {"from": "running", "event": "finish", "to": "done",
     "guard": {"key": "ok", "op": "==", "value": true},
     "set": {"finished": true}}
  ]
}

Guards: {"key", "op", "value"} with op in == != < <= > >= in not_in exists,
or {"all": [...]}, {"any": [...]}, {"not": {...}}.
"from" may be a string or a list of strings. Optional "set" merges a dict
into the context when the transition is taken.

Usage:
  state_machine.py validate machine.json
  state_machine.py run machine.json EVENT [EVENT ...] [--context JSON] [--history]
"""
import argparse
import json
import operator
import sys

OPS = {
    "==": operator.eq, "!=": operator.ne,
    "<": operator.lt, "<=": operator.le,
    ">": operator.gt, ">=": operator.ge,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


class MachineError(Exception):
    pass


def _from_states(t):
    f = t.get("from")
    return f if isinstance(f, list) else [f]


def validate_guard(g, where):
    errors = []
    if not isinstance(g, dict):
        return [f"{where}: guard must be an object"]
    if "all" in g or "any" in g:
        k = "all" if "all" in g else "any"
        if not isinstance(g[k], list):
            return [f"{where}: '{k}' must be a list"]
        for i, sub in enumerate(g[k]):
            errors += validate_guard(sub, f"{where}.{k}[{i}]")
    elif "not" in g:
        errors += validate_guard(g["not"], f"{where}.not")
    else:
        if not isinstance(g.get("key"), str):
            errors.append(f"{where}: guard needs a string 'key'")
        op = g.get("op", "==")
        if op != "exists":
            if op not in OPS:
                errors.append(f"{where}: unknown guard op {op!r}")
            if "value" not in g:
                errors.append(f"{where}: guard needs a 'value'")
    return errors


def validate(defn):
    """Return a list of error strings (empty if the definition is valid)."""
    if not isinstance(defn, dict):
        return ["definition must be a JSON object"]
    errors = []
    states = defn.get("states")
    if not isinstance(states, list) or not states:
        return ["'states' must be a non-empty list"]
    if not all(isinstance(s, str) for s in states):
        return ["'states' must contain only strings"]
    if len(set(states)) != len(states):
        errors.append("duplicate state names in 'states'")
    known = set(states)

    initial = defn.get("initial")
    if not initial:
        errors.append("missing initial state")
    elif initial not in known:
        errors.append(f"unknown initial state {initial!r}")

    final = defn.get("final", [])
    if not isinstance(final, list):
        errors.append("'final' must be a list")
        final = []
    for s in final:
        if s not in known:
            errors.append(f"unknown final state {s!r}")

    transitions = defn.get("transitions", [])
    if not isinstance(transitions, list):
        return errors + ["'transitions' must be a list"]
    edges = {}
    for i, t in enumerate(transitions):
        where = f"transition #{i}"
        if not isinstance(t, dict):
            errors.append(f"{where}: must be an object")
            continue
        if not isinstance(t.get("event"), str) or not t.get("event"):
            errors.append(f"{where}: missing event")
        srcs = _from_states(t)
        for s in srcs:
            if s not in known:
                errors.append(f"{where}: unknown source state {s!r}")
            elif s in final:
                errors.append(f"{where}: transition out of final state {s!r}")
        dst = t.get("to")
        if dst not in known:
            errors.append(f"{where}: unknown target state {dst!r}")
        for s in srcs:
            edges.setdefault(s, set()).add(dst)
        if "guard" in t:
            errors += validate_guard(t["guard"], f"{where} guard")
        if "set" in t and not isinstance(t["set"], dict):
            errors.append(f"{where}: 'set' must be an object")

    if initial in known:
        seen, stack = set(), [initial]
        while stack:
            s = stack.pop()
            if s in seen:
                continue
            seen.add(s)
            stack.extend(edges.get(s, ()))
        for s in states:
            if s not in seen:
                errors.append(f"unreachable state {s!r}")
    return errors


def eval_guard(g, ctx):
    if "all" in g:
        return all(eval_guard(x, ctx) for x in g["all"])
    if "any" in g:
        return any(eval_guard(x, ctx) for x in g["any"])
    if "not" in g:
        return not eval_guard(g["not"], ctx)
    op = g.get("op", "==")
    if op == "exists":
        return g["key"] in ctx
    if g["key"] not in ctx:
        return False
    try:
        return bool(OPS[op](ctx[g["key"]], g["value"]))
    except TypeError:
        return False


class StateMachine:
    def __init__(self, defn, context=None):
        errors = validate(defn)
        if errors:
            raise MachineError("invalid machine:\n  " + "\n  ".join(errors))
        self.initial = defn["initial"]
        self.final = set(defn.get("final", []))
        self.transitions = defn.get("transitions", [])
        self.state = self.initial
        self.context = dict(context or {})
        self.history = []  # dicts: step, event, from, to, status, context

    @property
    def done(self):
        return self.state in self.final

    def send(self, event):
        """Process one event. Returns True if a transition was taken."""
        step = len(self.history) + 1
        rec = {"step": step, "event": event, "from": self.state, "to": self.state}
        if self.done:
            rec["status"] = "rejected (machine is in a final state)"
            self.history.append(rec)
            return False
        candidates = [t for t in self.transitions
                      if t["event"] == event and self.state in _from_states(t)]
        if not candidates:
            rec["status"] = "ignored (no transition for event)"
            self.history.append(rec)
            return False
        for t in candidates:
            if "guard" not in t or eval_guard(t["guard"], self.context):
                self.context.update(t.get("set", {}))
                rec["to"] = t["to"]
                rec["status"] = "ok"
                rec["context"] = dict(self.context)
                self.state = t["to"]
                self.history.append(rec)
                return True
        rec["status"] = "blocked (guard failed)"
        self.history.append(rec)
        return False

    def format_history(self):
        lines = [f"{'#':>3}  {'event':<14} {'from':<14} {'to':<14} status"]
        for r in self.history:
            lines.append(f"{r['step']:>3}  {r['event']:<14} {r['from']:<14} "
                         f"{r['to']:<14} {r['status']}")
        return "\n".join(lines)


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except OSError as e:
        raise MachineError(f"cannot read {path}: {e.strerror}")
    except json.JSONDecodeError as e:
        raise MachineError(f"{path}: invalid JSON: {e}")


def main(argv=None):
    p = argparse.ArgumentParser(description="JSON-driven state machine runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a machine definition")
    v.add_argument("machine")
    r = sub.add_parser("run", help="run events against a machine")
    r.add_argument("machine")
    r.add_argument("events", nargs="*")
    r.add_argument("--context", default="{}", help="initial context as JSON object")
    r.add_argument("--history", action="store_true", help="print transition history")
    args = p.parse_args(argv)

    try:
        defn = load(args.machine)
        if args.cmd == "validate":
            errors = validate(defn)
            if errors:
                print("\n".join(f"error: {e}" for e in errors), file=sys.stderr)
                return 1
            print("valid")
            return 0
        try:
            ctx = json.loads(args.context)
        except json.JSONDecodeError as e:
            raise MachineError(f"--context: invalid JSON: {e}")
        if not isinstance(ctx, dict):
            raise MachineError("--context must be a JSON object")
        m = StateMachine(defn, ctx)
    except MachineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for ev in args.events:
        m.send(ev)
    if args.history:
        print(m.format_history())
    print(f"final state: {m.state}" + (" (final)" if m.done else ""))
    print(f"context: {json.dumps(m.context)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
