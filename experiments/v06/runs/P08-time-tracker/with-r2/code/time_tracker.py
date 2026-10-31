#!/usr/bin/env python3
"""Time tracker CLI: start <project>, stop, log, report. Stdlib only."""
import argparse
import json
import os
import sys
from datetime import datetime

FMT = "%Y-%m-%dT%H:%M:%S"


def default_path():
    return os.environ.get("TIME_TRACKER_FILE") or os.path.expanduser("~/.time_tracker.json")


def format_duration(seconds):
    seconds = max(0, int(seconds))
    return "%02d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["sessions"]


def save(path, sessions):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"sessions": sessions}, f, indent=2)
    os.replace(tmp, path)


def active(sessions):
    return next((s for s in sessions if s.get("end") is None), None)


def span(s, now):
    a = datetime.strptime(s["start"], FMT)
    b = datetime.strptime(s["end"], FMT) if s.get("end") else now
    return a, b


def overlaps(sessions, now):
    """Index pairs (i, j) of sessions whose intervals intersect with positive length."""
    spans = [span(s, now) for s in sessions]
    out = []
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            if spans[i][0] < spans[j][1] and spans[j][0] < spans[i][1]:
                out.append((i, j))
    return out


def main(argv=None, now=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    p = argparse.ArgumentParser(prog="time_tracker")
    p.add_argument("--file", default=None, help="JSON data file")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("start")
    sp.add_argument("project")
    sub.add_parser("stop")
    sub.add_parser("log")
    sub.add_parser("report")
    args = p.parse_args(argv)
    path = args.file or default_path()
    now = (now or datetime.now()).replace(microsecond=0)
    sessions = load(path)

    if args.cmd == "start":
        cur = active(sessions)
        if cur:
            print("error: session already active for '%s' since %s" % (cur["project"], cur["start"]), file=err)
            return 1
        sessions.append({"project": args.project, "start": now.strftime(FMT), "end": None})
        save(path, sessions)
        print("Started %s at %s" % (args.project, now.strftime(FMT)), file=out)
    elif args.cmd == "stop":
        cur = active(sessions)
        if not cur:
            print("error: no active session", file=err)
            return 1
        cur["end"] = now.strftime(FMT)
        save(path, sessions)
        a, b = span(cur, now)
        print("Stopped %s: %s" % (cur["project"], format_duration((b - a).total_seconds())), file=out)
    elif args.cmd == "log":
        bad = {k for pair in overlaps(sessions, now) for k in pair}
        for i, s in enumerate(sessions):
            a, b = span(s, now)
            print("%s  %s  %s  %s  %s%s" % (
                s["project"], s["start"], s["end"] or "(active)",
                format_duration((b - a).total_seconds()), "", "  OVERLAP" if i in bad else ""), file=out)
        for i, j in overlaps(sessions, now):
            print("warning: sessions %d (%s) and %d (%s) overlap" % (
                i + 1, sessions[i]["project"], j + 1, sessions[j]["project"]), file=out)
    elif args.cmd == "report":
        totals = {}
        for s in sessions:
            a, b = span(s, now)
            totals[s["project"]] = totals.get(s["project"], 0) + (b - a).total_seconds()
        for proj in sorted(totals):
            print("%s  %s" % (proj, format_duration(totals[proj])), file=out)
        for i, j in overlaps(sessions, now):
            print("warning: sessions %d and %d overlap; totals may double count" % (i + 1, j + 1), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
