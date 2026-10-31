#!/usr/bin/env python3
"""Simple time tracker CLI.

Usage:
    time_tracker.py start <project>
    time_tracker.py stop
    time_tracker.py log
    time_tracker.py report

Data is stored in a JSON file (default: ~/.time_tracker.json, override with
--file or the TIME_TRACKER_FILE environment variable).
"""
import argparse
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime

DEFAULT_FILE = os.path.join(os.path.expanduser("~"), ".time_tracker.json")


def now():
    return datetime.now().astimezone().replace(microsecond=0)


def parse(ts):
    return datetime.fromisoformat(ts)


def fmt_duration(seconds):
    seconds = int(seconds)
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h:02d}:{m:02d}:{s:02d}"


def load(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        sessions = data["sessions"] if isinstance(data, dict) else data
        for s in sessions:
            s["project"], parse(s["start"])
            if s.get("end") is not None:
                parse(s["end"])
        return sessions
    except (ValueError, KeyError, TypeError) as e:
        sys.exit(f"error: corrupt data file {path}: {e}")


def save(path, sessions):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"sessions": sessions}, f, indent=2)
    os.replace(tmp, path)


def active(sessions):
    return next((s for s in sessions if s.get("end") is None), None)


def duration(s, at=None):
    end = parse(s["end"]) if s.get("end") else (at or now())
    return (end - parse(s["start"])).total_seconds()


def find_overlaps(sessions):
    """Return list of (a, b) index pairs of overlapping sessions."""
    t = now()
    spans = sorted(
        (parse(s["start"]), parse(s["end"]) if s.get("end") else t, i)
        for i, s in enumerate(sessions)
    )
    pairs = []
    for i, (s1, e1, i1) in enumerate(spans):
        for s2, e2, i2 in spans[i + 1:]:
            if s2 >= e1:
                break
            pairs.append((i1, i2))
    return pairs


def cmd_start(args, sessions):
    cur = active(sessions)
    if cur:
        sys.exit(
            f"error: session for '{cur['project']}' already active "
            f"since {cur['start']}; stop it first"
        )
    project = args.project.strip()
    if not project:
        sys.exit("error: project name must not be empty")
    t = now()
    # A new open session overlaps any recorded session ending after now.
    for s in sessions:
        if s.get("end") and parse(s["end"]) > t:
            sys.exit(f"error: would overlap existing session for '{s['project']}'")
    sessions.append({"project": project, "start": t.isoformat(), "end": None})
    print(f"Started '{project}' at {t:%Y-%m-%d %H:%M:%S}")
    return True


def cmd_stop(args, sessions):
    cur = active(sessions)
    if not cur:
        sys.exit("error: no active session")
    t = now()
    if t < parse(cur["start"]):
        sys.exit("error: clock is earlier than session start; cannot stop")
    cur["end"] = t.isoformat()
    print(f"Stopped '{cur['project']}' after {fmt_duration(duration(cur))}")
    return True


def cmd_log(args, sessions):
    if not sessions:
        print("No sessions recorded.")
        return False
    overlaps = find_overlaps(sessions)
    flagged = {i for p in overlaps for i in p}
    print(f"{'PROJECT':<20} {'START':<19} {'END':<19} DURATION")
    for i, s in sorted(enumerate(sessions), key=lambda x: parse(x[1]["start"])):
        end = parse(s["end"]).strftime("%Y-%m-%d %H:%M:%S") if s.get("end") else "(active)"
        mark = "  !overlap" if i in flagged else ""
        print(
            f"{s['project']:<20} {parse(s['start']):%Y-%m-%d %H:%M:%S} "
            f"{end:<19} {fmt_duration(duration(s))}{mark}"
        )
    if overlaps:
        print("\nWarning: overlapping sessions detected:")
        for a, b in overlaps:
            print(f"  '{sessions[a]['project']}' ({sessions[a]['start']}) overlaps "
                  f"'{sessions[b]['project']}' ({sessions[b]['start']})")
    return False


def cmd_report(args, sessions):
    if not sessions:
        print("No sessions recorded.")
        return False
    totals = OrderedDict()
    for s in sessions:
        totals[s["project"]] = totals.get(s["project"], 0) + duration(s)
    width = max(len(p) for p in totals)
    for p, secs in sorted(totals.items(), key=lambda x: (-x[1], x[0])):
        print(f"{p:<{width}}  {fmt_duration(secs)}")
    print(f"{'TOTAL':<{width}}  {fmt_duration(sum(totals.values()))}")
    if find_overlaps(sessions):
        print("\nWarning: overlapping sessions detected; totals may double-count "
              "time. See 'log'.")
    return False


def main(argv=None):
    p = argparse.ArgumentParser(description="Simple time tracker")
    p.add_argument("--file", default=os.environ.get("TIME_TRACKER_FILE", DEFAULT_FILE),
                   help="JSON data file (default: %(default)s)")
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("start", help="start a session")
    sp.add_argument("project")
    sub.add_parser("stop", help="stop the active session")
    sub.add_parser("log", help="list all sessions")
    sub.add_parser("report", help="total time per project")
    args = p.parse_args(argv)

    sessions = load(args.file)
    handler = {"start": cmd_start, "stop": cmd_stop, "log": cmd_log, "report": cmd_report}
    if handler[args.command](args, sessions):
        save(args.file, sessions)


if __name__ == "__main__":
    main()
