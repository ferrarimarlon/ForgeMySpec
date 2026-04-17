#!/usr/bin/env python3
"""Time Tracker CLI — WITHOUT framework. Direct implementation."""
import argparse
import json
import os
import sys
from datetime import datetime

FILE = "sessions.json"
FMT = "%Y-%m-%dT%H:%M:%S"

def load():
    if os.path.exists(FILE): return json.load(open(FILE))
    return []

def save(s): json.dump(s, open(FILE, "w"), indent=2)

def fmt_dur(secs):
    return f"{secs//3600:02d}:{(secs%3600)//60:02d}:{secs%60:02d}"

def active(sessions):
    for s in sessions:
        if s.get("end") is None: return s
    return None

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
s = sub.add_parser("start"); s.add_argument("project")
sub.add_parser("stop"); sub.add_parser("status"); sub.add_parser("log")
r = sub.add_parser("report")
r.add_argument("--project"); r.add_argument("--date")

args = parser.parse_args()
sessions = load()

if args.cmd == "start":
    if active(sessions):
        print("Error: session already running", file=sys.stderr); sys.exit(1)
    sessions.append({"project": args.project, "start": datetime.now().strftime(FMT), "end": None, "duration_seconds": None})
    save(sessions)
    print(f"Started: {args.project}")

elif args.cmd == "stop":
    a = active(sessions)
    if not a: print("No active session", file=sys.stderr); sys.exit(1)
    now = datetime.now()
    dur = int((now - datetime.strptime(a["start"], FMT)).total_seconds())
    a["end"] = now.strftime(FMT)
    a["duration_seconds"] = dur
    save(sessions)
    print(f"Stopped. Duration: {fmt_dur(dur)}")

elif args.cmd == "status":
    a = active(sessions)
    if not a: print("No active session")
    else:
        elapsed = int((datetime.now() - datetime.strptime(a["start"], FMT)).total_seconds())
        print(f"Active: {a['project']} — elapsed {fmt_dur(elapsed)}")

elif args.cmd == "log":
    if not sessions: print("No sessions"); sys.exit(0)
    print(f"{'Project':<20} {'Start':<20} {'Duration'}")
    for s in sessions:
        dur = fmt_dur(s["duration_seconds"]) if s.get("duration_seconds") else "(active)"
        print(f"{s['project']:<20} {s['start']:<20} {dur}")

elif args.cmd == "report":
    completed = [s for s in sessions if s.get("duration_seconds") is not None]
    if args.project: completed = [s for s in completed if s["project"] == args.project]
    if args.date: completed = [s for s in completed if s["start"].startswith(args.date)]
    totals = {}
    for s in completed:
        totals[s["project"]] = totals.get(s["project"], 0) + s["duration_seconds"]
    if not totals: print("No sessions found"); sys.exit(0)
    for proj, secs in sorted(totals.items()):
        print(f"{proj:<20} {fmt_dur(secs)}")
