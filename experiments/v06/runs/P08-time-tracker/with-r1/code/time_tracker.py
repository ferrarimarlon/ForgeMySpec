#!/usr/bin/env python3
"""Time tracker CLI: start <project>, stop, log, report. Stdlib only.

Sessions live in a JSON file: {"sessions": [{"project", "start", "end"}]}.
Timestamps are ISO 8601 (UTC); the active session has "end": null.

Data file: --file, else $TIME_TRACKER_FILE, else ./time_tracker.json.
Exit codes: 0 success, 1 refused operation, 2 corrupt data file or bad usage.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

DEFAULT_FILE = "time_tracker.json"


class DataError(Exception):
    """The data file is corrupt or malformed."""


def format_duration(seconds):
    """Format a number of seconds as HH:MM:SS (hours may exceed 99)."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _parse_ts(value, where):
    if not isinstance(value, str):
        raise DataError(f"{where}: timestamp must be a string")
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        raise DataError(f"{where}: invalid timestamp {value!r}") from None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _fmt_ts(ts):
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def load_sessions(path):
    """Return a list of dicts {project, start, end(None|datetime)} sorted by file order."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise DataError(f"cannot read {path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        raise DataError(f"{path}: expected an object with a 'sessions' list")
    sessions = []
    for i, raw in enumerate(data["sessions"], 1):
        where = f"{path}: session {i}"
        if not isinstance(raw, dict):
            raise DataError(f"{where}: must be an object")
        project = raw.get("project")
        if not isinstance(project, str) or not project:
            raise DataError(f"{where}: missing project")
        start = _parse_ts(raw.get("start"), where)
        end = None if raw.get("end") is None else _parse_ts(raw.get("end"), where)
        if end is not None and end < start:
            raise DataError(f"{where}: end before start")
        sessions.append({"project": project, "start": start, "end": end})
    if sum(1 for s in sessions if s["end"] is None) > 1:
        raise DataError(f"{path}: more than one active session")
    return sessions


def save_sessions(path, sessions):
    """Write sessions atomically (temp file + rename)."""
    data = {
        "sessions": [
            {
                "project": s["project"],
                "start": _fmt_ts(s["start"]),
                "end": None if s["end"] is None else _fmt_ts(s["end"]),
            }
            for s in sessions
        ]
    }
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _active(sessions):
    for s in sessions:
        if s["end"] is None:
            return s
    return None


def _end_of(session, now):
    return session["end"] if session["end"] is not None else max(now, session["start"])


def _duration(session, now):
    return (_end_of(session, now) - session["start"]).total_seconds()


def find_overlaps(sessions, now):
    """Return the set of indexes of sessions that overlap another session.

    Two sessions overlap when each starts before the other ends; an active
    session ends at ``now``. Adjacent sessions (end == start) do not overlap.
    """
    flagged = set()
    for i, a in enumerate(sessions):
        for j in range(i + 1, len(sessions)):
            b = sessions[j]
            if a["start"] < _end_of(b, now) and b["start"] < _end_of(a, now):
                flagged.update((i, j))
    return flagged


def cmd_start(path, project, now):
    if not project.strip():
        print("error: project name must not be empty", file=sys.stderr)
        return 2
    sessions = load_sessions(path)
    active = _active(sessions)
    if active is not None:
        print(
            f"error: a session is already active (project {active['project']!r}, "
            f"started {_fmt_ts(active['start'])}); run 'stop' first",
            file=sys.stderr,
        )
        return 1
    sessions.append({"project": project, "start": now, "end": None})
    save_sessions(path, sessions)
    print(f"Started {project} at {_fmt_ts(now)}")
    return 0


def cmd_stop(path, now):
    sessions = load_sessions(path)
    active = _active(sessions)
    if active is None:
        print("error: no active session", file=sys.stderr)
        return 1
    active["end"] = max(now, active["start"])
    save_sessions(path, sessions)
    print(f"Stopped {active['project']} at {_fmt_ts(active['end'])} "
          f"({format_duration(_duration(active, now))})")
    return 0


def cmd_log(path, now):
    sessions = load_sessions(path)
    if not sessions:
        print("No sessions.")
        return 0
    flagged = find_overlaps(sessions, now)
    order = sorted(range(len(sessions)), key=lambda i: sessions[i]["start"])
    for i in order:
        s = sessions[i]
        end = "(active)" if s["end"] is None else _fmt_ts(s["end"])
        mark = "  [OVERLAP]" if i in flagged else ""
        print(f"{_fmt_ts(s['start'])}  {end}  {format_duration(_duration(s, now))}  "
              f"{s['project']}{mark}")
    if flagged:
        print(f"WARNING: {len(flagged)} overlapping sessions detected")
    return 0


def cmd_report(path, now):
    sessions = load_sessions(path)
    if not sessions:
        print("No sessions.")
        return 0
    totals = {}
    for s in sessions:
        totals[s["project"]] = totals.get(s["project"], 0) + _duration(s, now)
    width = max(len(p) for p in totals)
    for project in sorted(totals):
        print(f"{project:<{width}}  {format_duration(totals[project])}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="time_tracker", description="Track work sessions per project.")
    parser.add_argument("--file", help="JSON data file (default: $TIME_TRACKER_FILE or ./time_tracker.json)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_start = sub.add_parser("start", help="start a session for a project")
    p_start.add_argument("project")
    sub.add_parser("stop", help="stop the active session")
    sub.add_parser("log", help="list sessions, flagging overlaps")
    sub.add_parser("report", help="total time per project")
    return parser


def main(argv=None, now=None):
    args = build_parser().parse_args(argv)
    path = args.file or os.environ.get("TIME_TRACKER_FILE") or DEFAULT_FILE
    now = now or datetime.now(timezone.utc)
    try:
        if args.command == "start":
            return cmd_start(path, args.project, now)
        if args.command == "stop":
            return cmd_stop(path, now)
        if args.command == "log":
            return cmd_log(path, now)
        return cmd_report(path, now)
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
