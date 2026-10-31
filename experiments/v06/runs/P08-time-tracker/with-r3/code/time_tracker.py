#!/usr/bin/env python3
"""Time tracker CLI: start <project>, stop, log, report. Stdlib only."""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime

DEFAULT_FILE = "time_tracker.json"
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


class TrackerError(Exception):
    pass


def now():
    return datetime.now().replace(microsecond=0)


def format_duration(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%02d:%02d:%02d" % (h, m, s)


def _parse(ts):
    return datetime.strptime(ts, TS_FORMAT)


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"sessions": []}
    except (OSError, ValueError) as exc:
        raise TrackerError("cannot read %s: %s" % (path, exc))
    try:
        sessions = data["sessions"]
        if not isinstance(sessions, list):
            raise ValueError("sessions is not a list")
        for s in sessions:
            if not isinstance(s["project"], str):
                raise ValueError("bad project")
            _parse(s["start"])
            if s.get("end") is not None:
                _parse(s["end"])
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise TrackerError("corrupt data file %s: %s" % (path, exc))
    return data


def save(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tt-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def active_session(data):
    for s in data["sessions"]:
        if s.get("end") is None:
            return s
    return None


def _intervals(data, current):
    out = []
    for i, s in enumerate(data["sessions"]):
        start = _parse(s["start"])
        end = _parse(s["end"]) if s.get("end") is not None else current
        out.append((i, s["project"], start, end, s.get("end") is None))
    return out


def find_overlaps(intervals):
    """Pairs (i, j), i < j, whose intervals intersect with positive length."""
    pairs = []
    for a in range(len(intervals)):
        for b in range(a + 1, len(intervals)):
            if intervals[a][2] < intervals[b][3] and intervals[b][2] < intervals[a][3]:
                pairs.append((intervals[a][0], intervals[b][0]))
    return pairs


def cmd_start(args, data, out):
    act = active_session(data)
    if act is not None:
        raise TrackerError("a session is already active: %s (started %s)"
                           % (act["project"], act["start"]))
    t = now().strftime(TS_FORMAT)
    data["sessions"].append({"project": args.project, "start": t, "end": None})
    save(args.file, data)
    print("Started %s at %s" % (args.project, t), file=out)


def cmd_stop(args, data, out):
    act = active_session(data)
    if act is None:
        raise TrackerError("no active session")
    end = now()
    start = _parse(act["start"])
    if end < start:
        end = start
    act["end"] = end.strftime(TS_FORMAT)
    save(args.file, data)
    print("Stopped %s: %s" % (act["project"], format_duration((end - start).total_seconds())), file=out)


def cmd_log(args, data, out):
    ivs = _intervals(data, now())
    if not ivs:
        print("No sessions.", file=out)
        return
    overl = {}
    for i, j in find_overlaps(ivs):
        overl.setdefault(i, []).append(j + 1)
        overl.setdefault(j, []).append(i + 1)
    for i, project, start, end, running in ivs:
        line = "#%d %s %s -> %s %s" % (
            i + 1, project, start.strftime(TS_FORMAT),
            "(active)" if running else end.strftime(TS_FORMAT),
            format_duration((end - start).total_seconds()))
        if i in overl:
            line += "  OVERLAP with " + ", ".join("#%d" % n for n in sorted(overl[i]))
        print(line, file=out)


def cmd_report(args, data, out):
    totals = {}
    for _, project, start, end, _ in _intervals(data, now()):
        totals[project] = totals.get(project, 0) + max(0, (end - start).total_seconds())
    if not totals:
        print("No sessions.", file=out)
        return
    for project in sorted(totals):
        print("%s %s" % (project, format_duration(totals[project])), file=out)


def build_parser():
    p = argparse.ArgumentParser(prog="time_tracker", description="Simple time tracker.")
    p.add_argument("--file", default=os.environ.get("TIME_TRACKER_FILE", DEFAULT_FILE),
                   help="JSON data file (default: %s or $TIME_TRACKER_FILE)" % DEFAULT_FILE)
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("start", help="start a session")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the active session").set_defaults(func=cmd_stop)
    sub.add_parser("log", help="list sessions").set_defaults(func=cmd_log)
    sub.add_parser("report", help="total time per project").set_defaults(func=cmd_report)
    return p


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start" and not args.project.strip():
            raise TrackerError("project name must not be empty")
        data = load(args.file)
        args.func(args, data, out)
    except TrackerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
