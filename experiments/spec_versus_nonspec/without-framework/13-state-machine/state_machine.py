#!/usr/bin/env python3
"""State Machine CLI — WITHOUT framework. Direct implementation."""
import argparse
import json
import sys
from collections import deque

def load(path):
    return json.load(open(path))

def validate(defn):
    errors = []
    states = defn.get("states", [])
    initial = defn.get("initial_state", "")
    transitions = defn.get("transitions", [])

    if initial not in states:
        errors.append(f"initial_state '{initial}' not found")

    # Check duplicates
    seen = {}
    for t in transitions:
        k = (t.get("from_state"), t.get("event"))
        if k in seen: errors.append(f"Duplicate: {k}")
        seen[k] = t

    # Unreachable via BFS
    reachable = set()
    q = deque([initial])
    while q:
        s = q.popleft()
        if s in reachable: continue
        reachable.add(s)
        for t in transitions:
            if t.get("from_state") == s and t.get("to_state") not in reachable:
                q.append(t["to_state"])
    for s in states:
        if s not in reachable:
            errors.append(f"Unreachable: '{s}'")
    return errors

def eval_guard(guard, ctx):
    for op in [">=","<=","!=","==",">","<"]:
        if op in guard:
            field, val = guard.split(op, 1)
            field = field.strip(); val = val.strip()
            try: val = int(val)
            except:
                try: val = float(val)
                except: val = val.strip("'\"")
            cv = ctx.get(field)
            if cv is None: return False
            if op == ">": return cv > val
            if op == "<": return cv < val
            if op == ">=": return cv >= val
            if op == "<=": return cv <= val
            if op == "==": return cv == val
            if op == "!=": return cv != val
    return True

def find_trans(defn, state, event, ctx):
    for t in defn.get("transitions", []):
        if t.get("from_state") == state and t.get("event") == event:
            g = t.get("guard_condition")
            if not g or eval_guard(g, ctx):
                return t
    return None

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
r = sub.add_parser("run"); r.add_argument("definition"); r.add_argument("--events")
v = sub.add_parser("validate"); v.add_argument("definition")
d = sub.add_parser("diagram"); d.add_argument("definition")

args = parser.parse_args()

if args.cmd == "validate":
    defn = load(args.definition)
    errs = validate(defn)
    if errs:
        print("INVALID:"); [print(f"  - {e}") for e in errs]; sys.exit(1)
    else: print("VALID")

elif args.cmd == "run":
    defn = load(args.definition)
    errs = validate(defn)
    if errs:
        print("Invalid definition:", errs, file=sys.stderr); sys.exit(1)
    state = defn["initial_state"]
    ctx = {}
    history = []
    events = []
    if args.events:
        events = [l.strip() for l in open(args.events) if l.strip() and not l.startswith("#")]
    else:
        print(f"Current state: {state}")
        try:
            while True:
                ev = input("> ").strip()
                if not ev: break
                events.append(ev)
        except (EOFError, KeyboardInterrupt): pass

    for ev in events:
        t = find_trans(defn, state, ev, ctx)
        if t is None:
            print(f"Invalid event '{ev}' in state '{state}'", file=sys.stderr); sys.exit(1)
        old = state; state = t["to_state"]
        history.append((ev, old, state))
        print(f"  {old} --[{ev}]--> {state}")
    print(f"\nFinal: {state}")

elif args.cmd == "diagram":
    defn = load(args.definition)
    states = defn.get("states", [])
    transitions = defn.get("transitions", [])
    events = sorted(set(t.get("event","") for t in transitions))
    table = {s: {e: "" for e in events} for s in states}
    for t in transitions:
        if t.get("from_state") in table and t.get("event") in table[t["from_state"]]:
            table[t["from_state"]][t["event"]] = t.get("to_state","")
    w = max((len(s) for s in states + events), default=8) + 2
    print(f"{'State':<{w}}" + "".join(f"{e:<{w}}" for e in events))
    print("-" * (w * (1 + len(events))))
    for s in states:
        print(f"{s:<{w}}" + "".join(f"{table[s][e]:<{w}}" for e in events))
