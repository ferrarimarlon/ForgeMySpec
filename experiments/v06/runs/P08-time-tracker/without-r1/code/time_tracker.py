#!/usr/bin/env python3
"""Time tracker CLI: start <project>, stop, log, report.

Sessions are stored in a JSON file (default ~/.time_tracker.json, override
with --file or the TIME_TRACKER_FILE environment variable).
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime

DEFAULT_FILE = os.path.join(os.path.expanduser("~"), ".time_tracker.json")


def now():
    return datetime.now().astimezone()


def format_duration(seconds):
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
        sessions = data["sessions"] if isinstance(data, dict) else data
        for s in sessions:
            s["project"], s["start"]
            s.setdefault("end", None)
        return sessions
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        sys.exit(f"error: {path} is not a valid time tracker file ({e!r})")


def save(path, sessions):
    # Atomic write so a crash can't corrupt the data file.
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".time_tracker.")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"sessions": sessions}, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def active_session(sessions):
    for s in sessions:
        if s["end"] is None:
            return s
    return None


def span(s, at):
    start = datetime.fromisoformat(s["start"])
    end = datetime.fromisoformat(s["end"]) if s["end"] else at
    return start, end


def find_overlaps(sessions, at):
    """Return list of (i, j) index pairs whose time ranges overlap."""
    spans = sorted(((span(s, at), i) for i, s in enumerate(sessions)),
                   key=lambda x: x[0][0])
    pairs = []
    for a in range(len(spans)):
        (_, end_a), i = spans[a]
        for b in range(a + 1, len(spans)):
            (start_b, _), j = spans[b]
            if start_b >= end_a:
                break
            pairs.append((min(i, j), max(i, j)))
    return sorted(pairs)


def cmd_start(args):
    sessions = load(args.file)
    cur = active_session(sessions)
    if cur:
        t = now()
        elapsed = (t - datetime.fromisoformat(cur["start"])).total_seconds()
        sys.exit(f"error: session already active for '{cur['project']}' "
                 f"(running {format_duration(elapsed)}). Run 'stop' first.")
    project = args.project.strip()
    if not project:
        sys.exit("error: project name must not be empty")
    t = now()
    new = {"project": project, "start": t.isoformat(), "end": None}
    # Clock changes or hand-edited files can make a new session overlap.
    for s in sessions:
        _, end = span(s, t)
        if end > t:
            sys.exit(f"error: starting now would overlap an existing "
                     f"'{s['project']}' session ending {end.isoformat()}")
    sessions.append(new)
    save(args.file, sessions)
    print(f"Started '{project}' at {t:%Y-%m-%d %H:%M:%S}")


def cmd_stop(args):
    sessions = load(args.file)
    cur = active_session(sessions)
    if not cur:
        sys.exit("error: no active session")
    t = now()
    start = datetime.fromisoformat(cur["start"])
    if t < start:
        sys.exit("error: clock is earlier than session start; cannot stop")
    cur["end"] = t.isoformat()
    save(args.file, sessions)
    print(f"Stopped '{cur['project']}'. Duration: "
          f"{format_duration((t - start).total_seconds())}")


def print_overlaps(sessions, at):
    pairs = find_overlaps(sessions, at)
    if not pairs:
        return
    print("\nWARNING: overlapping sessions detected:", file=sys.stderr)
    for i, j in pairs:
        a, b = sessions[i], sessions[j]
        print(f"  #{i + 1} {a['project']} and #{j + 1} {b['project']}",
              file=sys.stderr)


def cmd_log(args):
    sessions = load(args.file)
    if not sessions:
        print("No sessions recorded.")
        return
    t = now()
    print(f"{'#':>3}  {'PROJECT':<20} {'START':<19}  {'END':<19}  DURATION")
    for n, s in enumerate(sessions, 1):
        start, end = span(s, t)
        end_txt = end.strftime("%Y-%m-%d %H:%M:%S") if s["end"] else "(active)"
        print(f"{n:>3}  {s['project']:<20} {start:%Y-%m-%d %H:%M:%S}  "
              f"{end_txt:<19}  {format_duration((end - start).total_seconds())}")
    print_overlaps(sessions, t)


def cmd_report(args):
    sessions = load(args.file)
    if not sessions:
        print("No sessions recorded.")
        return
    t = now()
    totals = {}
    for s in sessions:
        start, end = span(s, t)
        totals[s["project"]] = totals.get(s["project"], 0) + \
            (end - start).total_seconds()
    width = max(len(p) for p in totals)
    for project, secs in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"{project:<{width}}  {format_duration(secs)}")
    print(f"{'TOTAL':<{width}}  {format_duration(sum(totals.values()))}")
    print_overlaps(sessions, t)


def build_parser():
    p = argparse.ArgumentParser(description="Simple time tracker.")
    p.add_argument("--file", default=os.environ.get("TIME_TRACKER_FILE",
                                                    DEFAULT_FILE),
                   help="JSON data file (default: %(default)s)")
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("start", help="start a session")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the active session").set_defaults(
        func=cmd_stop)
    sub.add_parser("log", help="list all sessions").set_defaults(func=cmd_log)
    sub.add_parser("report", help="total time per project").set_defaults(
        func=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
