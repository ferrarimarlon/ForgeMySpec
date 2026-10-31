#!/usr/bin/env python3
"""Simple time tracker CLI.

Usage:
    time_tracker.py start <project>
    time_tracker.py stop
    time_tracker.py log
    time_tracker.py report

Data file: $TIME_TRACKER_FILE or ~/.time_tracker.json (override with --file).
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime

DEFAULT_FILE = os.environ.get(
    "TIME_TRACKER_FILE", os.path.join(os.path.expanduser("~"), ".time_tracker.json")
)


def now():
    return datetime.now().astimezone()


def fmt_duration(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        sessions = data["sessions"]
        for s in sessions:
            datetime.fromisoformat(s["start"])
            if s.get("end"):
                datetime.fromisoformat(s["end"])
            s["project"]
    except (ValueError, KeyError, TypeError) as e:
        sys.exit(f"error: data file {path} is corrupt ({e!r})")
    return sessions


def save(path, sessions):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tt_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"sessions": sessions}, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parse(ts):
    return datetime.fromisoformat(ts)


def active(sessions):
    for s in sessions:
        if not s.get("end"):
            return s
    return None


def duration(s, at=None):
    end = parse(s["end"]) if s.get("end") else (at or now())
    return (end - parse(s["start"])).total_seconds()


def find_overlaps(sessions):
    """Return list of (a, b) index pairs whose time ranges overlap."""
    t = now()
    spans = []
    for i, s in enumerate(sessions):
        end = parse(s["end"]) if s.get("end") else t
        spans.append((parse(s["start"]), end, i))
    spans.sort()
    out = []
    for x in range(len(spans)):
        for y in range(x + 1, len(spans)):
            if spans[y][0] >= spans[x][1]:
                break
            out.append((spans[x][2], spans[y][2]))
    return sorted(out)


def cmd_start(args, path):
    project = args.project.strip()
    if not project:
        sys.exit("error: project name must not be empty")
    sessions = load(path)
    cur = active(sessions)
    if cur:
        sys.exit(
            f"error: session already active on '{cur['project']}' "
            f"(started {cur['start']}); run 'stop' first"
        )
    t = now()
    # Guard against a clock set before a recorded session's end.
    for s in sessions:
        if s.get("end") and parse(s["end"]) > t:
            print(f"warning: new session overlaps session on '{s['project']}'",
                  file=sys.stderr)
            break
    sessions.append({"project": project, "start": t.isoformat(timespec="seconds"),
                     "end": None})
    save(path, sessions)
    print(f"Started '{project}' at {t:%Y-%m-%d %H:%M:%S}")


def cmd_stop(args, path):
    sessions = load(path)
    cur = active(sessions)
    if not cur:
        sys.exit("error: no active session")
    t = now()
    if t < parse(cur["start"]):
        sys.exit("error: current time is before session start; check system clock")
    cur["end"] = t.isoformat(timespec="seconds")
    save(path, sessions)
    print(f"Stopped '{cur['project']}' — {fmt_duration(duration(cur))}")


def cmd_log(args, path):
    sessions = load(path)
    if not sessions:
        print("No sessions recorded.")
        return
    overlapping = set()
    pairs = find_overlaps(sessions)
    for a, b in pairs:
        overlapping.update((a, b))
    print(f"{'#':>3}  {'PROJECT':<20} {'START':<19}  {'END':<19}  {'DURATION':>8}")
    for i, s in enumerate(sessions, 1):
        start = parse(s["start"]).astimezone()
        end = parse(s["end"]).astimezone().strftime("%Y-%m-%d %H:%M:%S") if s.get("end") else "(running)"
        flag = "  !overlap" if (i - 1) in overlapping else ""
        print(f"{i:>3}  {s['project']:<20} {start:%Y-%m-%d %H:%M:%S}  {end:<19}  "
              f"{fmt_duration(duration(s)):>8}{flag}")
    if pairs:
        print("\nWarning: overlapping sessions detected:")
        for a, b in pairs:
            print(f"  #{a + 1} ({sessions[a]['project']}) overlaps "
                  f"#{b + 1} ({sessions[b]['project']})")


def cmd_report(args, path):
    sessions = load(path)
    if not sessions:
        print("No sessions recorded.")
        return
    totals = {}
    for s in sessions:
        totals[s["project"]] = totals.get(s["project"], 0) + duration(s)
    w = max(len("PROJECT"), max(len(p) for p in totals))
    print(f"{'PROJECT':<{w}}  {'TOTAL':>8}")
    for p, secs in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{p:<{w}}  {fmt_duration(secs):>8}")
    print(f"{'-' * w}  {'-' * 8}")
    print(f"{'TOTAL':<{w}}  {fmt_duration(sum(totals.values())):>8}")
    if find_overlaps(sessions):
        print("\nWarning: overlapping sessions detected; totals double-count "
              "overlapped time. See 'log'.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Simple time tracker")
    p.add_argument("--file", default=DEFAULT_FILE, help="JSON data file")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("start", help="start a session")
    sp.add_argument("project")
    sp.set_defaults(fn=cmd_start)
    sub.add_parser("stop", help="stop the active session").set_defaults(fn=cmd_stop)
    sub.add_parser("log", help="list all sessions").set_defaults(fn=cmd_log)
    sub.add_parser("report", help="total time per project").set_defaults(fn=cmd_report)
    args = p.parse_args(argv)
    args.fn(args, args.file)


if __name__ == "__main__":
    main()
