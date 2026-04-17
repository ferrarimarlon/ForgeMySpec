#!/usr/bin/env python3
"""State Machine CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: BFS unreachable detection, no eval() for guards, history tracking.
"""
import argparse
import json
import sys
from collections import deque
from typing import Any, Dict, List, Optional, Tuple


def load_definition(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def validate_definition(defn: dict) -> List[str]:
    """Validate state machine definition. Returns list of errors."""
    errors = []
    states = defn.get("states", [])
    initial = defn.get("initial_state", "")
    transitions = defn.get("transitions", [])

    if not states:
        errors.append("No states defined")
    if not initial:
        errors.append("No initial_state defined")
    elif initial not in states:
        errors.append(f"initial_state '{initial}' not in states list")

    # Check duplicate transitions (same from_state + event)
    seen_transitions = {}
    for t in transitions:
        key = (t.get("from_state"), t.get("event"))
        if key in seen_transitions:
            errors.append(
                f"Duplicate transition: from='{key[0]}' event='{key[1]}'"
            )
        else:
            seen_transitions[key] = t

    # Check all transition states exist
    for t in transitions:
        for field in ("from_state", "to_state"):
            s = t.get(field)
            if s and s not in states:
                errors.append(f"Transition references unknown state '{s}' (field: {field})")

    # Check unreachable states via BFS from initial_state
    if initial in states and not errors:
        reachable = set()
        queue = deque([initial])
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            for t in transitions:
                if t.get("from_state") == current:
                    dest = t.get("to_state")
                    if dest and dest not in reachable:
                        queue.append(dest)
        unreachable = set(states) - reachable
        for s in unreachable:
            errors.append(f"State '{s}' is unreachable from initial_state '{initial}'")

    return errors


def eval_guard(guard: str, context: dict) -> bool:
    """Evaluate simple guard: 'field op value'. No eval()."""
    ops = [">=", "<=", "!=", "==", ">", "<"]
    for op in ops:
        if op in guard:
            parts = guard.split(op, 1)
            field = parts[0].strip()
            raw_val = parts[1].strip()
            # Parse value
            try:
                val = int(raw_val)
            except ValueError:
                try:
                    val = float(raw_val)
                except ValueError:
                    # String comparison (strip quotes)
                    val = raw_val.strip("\"'")

            ctx_val = context.get(field)
            if ctx_val is None:
                return False
            try:
                if op == ">":
                    return ctx_val > val
                elif op == "<":
                    return ctx_val < val
                elif op == ">=":
                    return ctx_val >= val
                elif op == "<=":
                    return ctx_val <= val
                elif op == "==":
                    return ctx_val == val
                elif op == "!=":
                    return ctx_val != val
            except TypeError:
                return False
    return True  # No guard condition → always passes


def find_transition(defn: dict, current_state: str, event: str, context: dict) -> Optional[dict]:
    """Find the first matching transition for current state + event with passing guard."""
    for t in defn.get("transitions", []):
        if t.get("from_state") == current_state and t.get("event") == event:
            guard = t.get("guard_condition")
            if guard:
                if not eval_guard(guard, context):
                    continue
            return t
    return None


def cmd_run(args: argparse.Namespace) -> None:
    defn = load_definition(args.definition)
    errors = validate_definition(defn)
    if errors:
        print("Definition invalid:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    current_state = defn["initial_state"]
    history = []
    context = {}

    # Read events from file or interactively
    if args.events:
        with open(args.events) as f:
            events = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        print(f"State machine started. Current state: {current_state}")
        print("Enter events (Ctrl+C or empty line to quit):")
        events = []
        try:
            while True:
                ev = input("> ").strip()
                if not ev:
                    break
                events.append(ev)
        except (KeyboardInterrupt, EOFError):
            pass

    for event in events:
        transition = find_transition(defn, current_state, event, context)
        if transition is None:
            print(f"ERROR: Invalid event '{event}' for state '{current_state}'", file=sys.stderr)
            sys.exit(1)
        from_state = current_state
        current_state = transition["to_state"]
        history.append({"event": event, "from": from_state, "to": current_state})
        print(f"  [{event}] {from_state} → {current_state}")

    print(f"\nFinal state: {current_state}")
    print(f"History ({len(history)} transition(s)):")
    for h in history:
        print(f"  {h['from']} --[{h['event']}]--> {h['to']}")


def cmd_validate(args: argparse.Namespace) -> None:
    defn = load_definition(args.definition)
    errors = validate_definition(defn)
    if errors:
        print(f"Definition INVALID ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("Definition is VALID.")
        states = defn.get("states", [])
        transitions = defn.get("transitions", [])
        print(f"  States: {len(states)}, Transitions: {len(transitions)}, Initial: {defn.get('initial_state')}")


def cmd_diagram(args: argparse.Namespace) -> None:
    defn = load_definition(args.definition)
    states = defn.get("states", [])
    transitions = defn.get("transitions", [])

    # Collect all events
    events = sorted(set(t.get("event", "") for t in transitions))

    # Build transition table
    table = {s: {e: "" for e in events} for s in states}
    for t in transitions:
        fs = t.get("from_state", "")
        ev = t.get("event", "")
        ts = t.get("to_state", "")
        if fs in table and ev in table[fs]:
            table[fs][ev] = ts

    # Print ASCII table
    col_w = max(len(s) for s in states + events + ["State"]) + 2
    header = f"{'State':<{col_w}}" + "".join(f"{e:<{col_w}}" for e in events)
    print(header)
    print("-" * len(header))
    for s in states:
        row = f"{s:<{col_w}}" + "".join(f"{table[s][e]:<{col_w}}" for e in events)
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="State Machine CLI")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run state machine")
    p_run.add_argument("definition", help="State machine JSON definition")
    p_run.add_argument("--events", help="Events file (one per line)")

    p_val = sub.add_parser("validate", help="Validate state machine definition")
    p_val.add_argument("definition", help="State machine JSON definition")

    p_diag = sub.add_parser("diagram", help="Print ASCII transition table")
    p_diag.add_argument("definition", help="State machine JSON definition")

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "diagram":
        cmd_diagram(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
