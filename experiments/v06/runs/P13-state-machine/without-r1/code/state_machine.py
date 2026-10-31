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
     "guard": {"key": "progress", "op": ">=", "value": 100}},
    {"from": "running", "event": "tick", "to": "running",
     "set": {"progress": 100}}
  ]
}

Guard: {"key", "op", "value"} with op in ==, !=, <, <=, >, >=, in, not in,
or {"all": [guards]}, {"any": [guards]}, {"not": guard}.
Optional "set" on a transition updates the context when it fires.
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
    "not in": lambda a, b: a not in b,
}


class MachineError(Exception):
    pass


def check_guard(guard, ctx, errors=None, where=""):
    """Evaluate a guard against ctx. If errors is a list, validate shape only."""
    def bad(msg):
        if errors is not None:
            errors.append(f"{where}: {msg}")
        return False

    if not isinstance(guard, dict):
        return bad("guard must be an object")
    if "all" in guard or "any" in guard:
        name = "all" if "all" in guard else "any"
        subs = guard[name]
        if not isinstance(subs, list):
            return bad(f"'{name}' must be a list")
        results = [check_guard(g, ctx, errors, where) for g in subs]
        if errors is not None:
            return True
        return all(results) if name == "all" else any(results)
    if "not" in guard:
        r = check_guard(guard["not"], ctx, errors, where)
        return True if errors is not None else not r
    if "key" not in guard or "op" not in guard or "value" not in guard:
        return bad("guard needs 'key', 'op' and 'value'")
    if guard["op"] not in OPS:
        return bad(f"unknown guard operator {guard['op']!r}")
    if errors is not None:
        return True
    if guard["key"] not in ctx:
        return False
    try:
        return bool(OPS[guard["op"]](ctx[guard["key"]], guard["value"]))
    except TypeError:
        return False


class Machine:
    def __init__(self, definition):
        self.definition = definition
        self.states = definition.get("states", [])
        self.initial = definition.get("initial")
        self.final = definition.get("final", [])
        self.transitions = definition.get("transitions", [])
        self.state = self.initial
        self.context = {}
        self.history = []

    def validate(self):
        """Return a list of error strings (empty if valid)."""
        errs = []
        d = self.definition
        if not isinstance(d, dict):
            return ["definition must be a JSON object"]
        if not isinstance(self.states, list) or not all(isinstance(s, str) for s in self.states):
            return ["'states' must be a list of strings"]
        if not isinstance(self.final, list):
            return ["'final' must be a list"]
        if not isinstance(self.transitions, list):
            return ["'transitions' must be a list"]
        states = set(self.states)
        if len(states) != len(self.states):
            errs.append("duplicate state names")
        if not self.states:
            errs.append("no states defined")
        if not self.initial:
            errs.append("missing initial state")
        elif self.initial not in states:
            errs.append(f"unknown initial state {self.initial!r}")
        for f in self.final:
            if f not in states:
                errs.append(f"unknown final state {f!r}")
        edges = {}
        for i, t in enumerate(self.transitions):
            where = f"transition #{i}"
            if not isinstance(t, dict):
                errs.append(f"{where}: must be an object")
                continue
            for k in ("from", "event", "to"):
                if k not in t:
                    errs.append(f"{where}: missing '{k}'")
            src, dst = t.get("from"), t.get("to")
            if "from" in t and src not in states:
                errs.append(f"{where}: unknown source state {src!r}")
            if "to" in t and dst not in states:
                errs.append(f"{where}: unknown target state {dst!r}")
            if "guard" in t:
                check_guard(t["guard"], {}, errs, where)
            if "set" in t and not isinstance(t["set"], dict):
                errs.append(f"{where}: 'set' must be an object")
            edges.setdefault(src, set()).add(dst)
        if self.initial in states:
            seen, stack = set(), [self.initial]
            while stack:
                s = stack.pop()
                if s in seen:
                    continue
                seen.add(s)
                stack.extend(edges.get(s, ()))
            for s in self.states:
                if s not in seen:
                    errs.append(f"unreachable state {s!r}")
        return errs

    def is_final(self):
        return self.state in self.final

    def fire(self, event):
        """Fire an event. Returns the history entry; raises MachineError if rejected."""
        if self.is_final():
            raise MachineError(f"in final state {self.state!r}; event {event!r} rejected")
        candidates = [t for t in self.transitions
                      if t["from"] == self.state and t["event"] == event]
        if not candidates:
            raise MachineError(f"no transition from {self.state!r} on {event!r}")
        for t in candidates:
            if "guard" not in t or check_guard(t["guard"], self.context):
                self.context.update(t.get("set", {}))
                entry = {"step": len(self.history) + 1, "event": event,
                         "from": self.state, "to": t["to"],
                         "context": dict(self.context)}
                self.state = t["to"]
                self.history.append(entry)
                return entry
        raise MachineError(f"guard blocked {event!r} in state {self.state!r}")

    def format_history(self):
        if not self.history:
            return "(no transitions)"
        return "\n".join(
            f"{h['step']:>3}. {h['from']} --{h['event']}--> {h['to']}  ctx={json.dumps(h['context'], sort_keys=True)}"
            for h in self.history)


def main(argv=None):
    p = argparse.ArgumentParser(description="Run events against a JSON state machine.")
    p.add_argument("machine", help="path to machine definition JSON")
    p.add_argument("events", nargs="*", help="events to fire in order")
    p.add_argument("--context", default="{}", help="initial context as JSON object")
    p.add_argument("--validate", action="store_true", help="only validate the definition")
    p.add_argument("--history", action="store_true", help="print transition history at the end")
    p.add_argument("--strict", action="store_true", help="stop at the first rejected event")
    args = p.parse_args(argv)

    try:
        with open(args.machine) as f:
            definition = json.load(f)
        ctx = json.loads(args.context)
        if not isinstance(ctx, dict):
            raise ValueError("--context must be a JSON object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    m = Machine(definition)
    errs = m.validate()
    if errs:
        print("invalid machine:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    if args.validate:
        print("machine is valid")
        return 0

    m.context = ctx
    rc = 0
    print(f"start: {m.state}")
    for ev in args.events:
        try:
            h = m.fire(ev)
            print(f"{ev}: {h['from']} -> {h['to']}")
        except MachineError as e:
            print(f"{ev}: rejected ({e})", file=sys.stderr)
            rc = 3
            if args.strict:
                break
    print(f"end: {m.state}{' (final)' if m.is_final() else ''}")
    if args.history:
        print("history:")
        print(m.format_history())
    return rc


if __name__ == "__main__":
    sys.exit(main())
