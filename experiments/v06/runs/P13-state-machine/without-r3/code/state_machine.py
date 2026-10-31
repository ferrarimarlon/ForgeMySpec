#!/usr/bin/env python3
"""State machine CLI: load a JSON definition, validate it, run events, print history.

Machine definition:
{
  "states": ["idle", "running", "done"],
  "initial": "idle",
  "final": ["done"],
  "transitions": [
    {"from": "idle", "event": "start", "to": "running"},
    {"from": "running", "event": "finish", "to": "done",
     "guard": {"key": "progress", "op": ">=", "value": 100}}
  ]
}

A guard is a condition or a list of conditions (all must hold) on the context:
  {"key": "a.b", "op": "==", "value": 1}   ops: == != < <= > >= in not_in truthy falsy
Dotted keys look into nested dicts. Transitions are tried in file order; the
first whose guard passes wins.

Events on the command line are "name" or "name:key=value,key2=value2"; the
key/value pairs (values parsed as JSON when possible) are merged into the
context before guards are evaluated.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "truthy": lambda a, b: bool(a),
    "falsy": lambda a, b: not a,
}
_MISSING = object()


class MachineError(Exception):
    pass


def lookup(context, dotted):
    cur = context
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def check_condition(cond, context):
    """Evaluate one condition; a missing key or type mismatch is False."""
    actual = lookup(context, cond["key"])
    if actual is _MISSING:
        return cond["op"] in ("falsy", "!=", "not_in")
    try:
        return OPS[cond["op"]](actual, cond.get("value"))
    except TypeError:
        return False


def guard_passes(guard, context):
    if guard is None:
        return True
    conds = guard if isinstance(guard, list) else [guard]
    return all(check_condition(c, context) for c in conds)


def format_guard(guard):
    if guard is None:
        return ""
    conds = guard if isinstance(guard, list) else [guard]
    return " AND ".join(
        c["key"] if c["op"] == "truthy"
        else f"not {c['key']}" if c["op"] == "falsy"
        else f"{c['key']} {c['op']} {c.get('value')!r}"
        for c in conds
    )


def validate(defn):
    """Return a list of problems (empty if the definition is valid)."""
    errors = []
    if not isinstance(defn, dict):
        return ["definition must be a JSON object"]

    states = defn.get("states")
    if not isinstance(states, list) or not states or not all(isinstance(s, str) for s in states):
        return ["'states' must be a non-empty list of strings"]
    for s in sorted({s for s in states if states.count(s) > 1}):
        errors.append(f"duplicate state '{s}'")
    known = set(states)

    initial = defn.get("initial")
    if initial is None:
        errors.append("missing initial state")
    elif initial not in known:
        errors.append(f"unknown initial state '{initial}'")

    finals = defn.get("final", [])
    if not isinstance(finals, list):
        errors.append("'final' must be a list")
        finals = []
    for f in finals:
        if f not in known:
            errors.append(f"unknown final state '{f}'")

    transitions = defn.get("transitions", [])
    if not isinstance(transitions, list):
        errors.append("'transitions' must be a list")
        transitions = []
    edges = {}
    for i, t in enumerate(transitions):
        if not isinstance(t, dict):
            errors.append(f"transition #{i} must be an object")
            continue
        src, dst, ev = t.get("from"), t.get("to"), t.get("event")
        if src not in known:
            errors.append(f"transition #{i}: unknown source state {src!r}")
        if dst not in known:
            errors.append(f"transition #{i}: unknown target state {dst!r}")
        if not isinstance(ev, str) or not ev:
            errors.append(f"transition #{i}: missing event")
        if src in finals:
            errors.append(f"transition #{i}: leaves final state '{src}'")
        if "guard" in t:
            g = t["guard"]
            for c in (g if isinstance(g, list) else [g]):
                if not isinstance(c, dict) or not isinstance(c.get("key"), str):
                    errors.append(f"transition #{i}: guard condition needs a 'key'")
                elif c.get("op") not in OPS:
                    errors.append(f"transition #{i}: unknown guard op {c.get('op')!r}")
                elif c["op"] not in ("truthy", "falsy") and "value" not in c:
                    errors.append(f"transition #{i}: guard on '{c['key']}' needs a 'value'")
        edges.setdefault(src, []).append(dst)

    if initial in known:
        seen, stack = {initial}, [initial]
        while stack:
            for nxt in edges.get(stack.pop(), []):
                if nxt in known and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        for s in states:
            if s not in seen:
                errors.append(f"unreachable state '{s}'")
    return errors


@dataclass
class Record:
    step: int
    event: str
    source: str
    target: str  # equals source when rejected
    accepted: bool
    note: str = ""
    context: dict = field(default_factory=dict)


class StateMachine:
    def __init__(self, defn, context=None):
        errors = validate(defn)
        if errors:
            raise MachineError("\n".join(errors))
        self.transitions = defn.get("transitions", [])
        self.finals = set(defn.get("final", []))
        self.state = defn["initial"]
        self.context = dict(context or {})
        self.history = []

    @property
    def done(self):
        return self.state in self.finals

    def send(self, event, data=None):
        self.context.update(data or {})
        src = self.state
        accepted, target, note = False, src, ""
        if self.done:
            note = "machine is in a final state"
        else:
            candidates = [t for t in self.transitions if t["from"] == src and t["event"] == event]
            if not candidates:
                note = "no transition for event"
            else:
                for t in candidates:
                    if guard_passes(t.get("guard"), self.context):
                        accepted, target = True, t["to"]
                        note = f"guard: {format_guard(t.get('guard'))}" if t.get("guard") else ""
                        break
                else:
                    note = "guard failed: " + "; ".join(format_guard(t.get("guard")) for t in candidates)
        self.state = target
        rec = Record(len(self.history) + 1, event, src, target, accepted, note, json.loads(json.dumps(self.context)))
        self.history.append(rec)
        return rec

    def format_history(self):
        if not self.history:
            return "(no history)"
        lines = []
        for r in self.history:
            arrow = f"{r.source} -> {r.target}" if r.accepted else f"{r.source} -x"
            status = "ok" if r.accepted else "REJECTED"
            line = f"{r.step:>3}. [{status}] {r.event}: {arrow}"
            if r.note:
                line += f"  ({r.note})"
            lines.append(line)
        return "\n".join(lines)


def parse_event(text):
    """'name' or 'name:k=v,k2=v2' -> (name, data dict)."""
    name, _, rest = text.partition(":")
    name, data = name.strip(), {}
    if rest:
        for pair in rest.split(","):
            k, sep, v = pair.partition("=")
            if not sep or not k.strip():
                raise MachineError(f"bad event payload in {text!r}: expected key=value")
            try:
                data[k.strip()] = json.loads(v)
            except json.JSONDecodeError:
                data[k.strip()] = v
    if not name:
        raise MachineError(f"empty event name in {text!r}")
    return name, data


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except OSError as e:
        raise MachineError(f"cannot read {path}: {e.strerror}")
    except json.JSONDecodeError as e:
        raise MachineError(f"invalid JSON in {path}: {e}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Run events against a JSON-defined state machine.")
    p.add_argument("machine", help="path to machine definition JSON")
    p.add_argument("events", nargs="*", help="events: name or name:key=value,...")
    p.add_argument("-f", "--events-file", help="file with one event per line (# comments allowed)")
    p.add_argument("-c", "--context", default="{}", help="initial context as a JSON object")
    p.add_argument("--validate-only", action="store_true", help="validate and exit")
    p.add_argument("--strict", action="store_true", help="stop at first rejected event (exit 1)")
    p.add_argument("--json", action="store_true", help="print history as JSON")
    args = p.parse_args(argv)

    try:
        defn = load_json(args.machine)
        errors = validate(defn)
        if errors:
            print(f"{args.machine}: invalid machine definition", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 2
        if args.validate_only:
            print(f"{args.machine}: valid")
            return 0

        try:
            ctx = json.loads(args.context)
        except json.JSONDecodeError as e:
            raise MachineError(f"--context is not valid JSON: {e}")
        if not isinstance(ctx, dict):
            raise MachineError("--context must be a JSON object")

        events = list(args.events)
        if args.events_file:
            try:
                with open(args.events_file) as f:
                    events += [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
            except OSError as e:
                raise MachineError(f"cannot read {args.events_file}: {e.strerror}")
        parsed = [parse_event(e) for e in events]
    except MachineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    sm = StateMachine(defn, ctx)
    rejected = False
    for name, data in parsed:
        rec = sm.send(name, data)
        if not rec.accepted:
            rejected = True
            if args.strict:
                break

    if args.json:
        print(json.dumps({
            "final_state": sm.state, "in_final_state": sm.done, "context": sm.context,
            "history": [r.__dict__ for r in sm.history],
        }, indent=2))
    else:
        print(sm.format_history())
        print(f"\nfinal state: {sm.state}{' (final)' if sm.done else ''}")
        print(f"context: {json.dumps(sm.context)}")
    return 1 if (rejected and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
