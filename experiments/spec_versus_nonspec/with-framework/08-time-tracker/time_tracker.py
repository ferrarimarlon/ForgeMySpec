#!/usr/bin/env python3
"""Time Tracker CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: overlap detection, HH:MM:SS format, project/date report.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional

DATA_FILE = "sessions.json"
DT_FMT = "%Y-%m-%dT%H:%M:%S"


def load_sessions(path: str) -> List[dict]:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_sessions(sessions: List[dict], path: str) -> None:
    with open(path, "w") as f:
        json.dump(sessions, f, indent=2)


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def find_active(sessions: List[dict]) -> Optional[dict]:
    for s in sessions:
        if s.get("end") is None:
            return s
    return None


def cmd_start(args: argparse.Namespace) -> None:
    sessions = load_sessions(args.file)
    active = find_active(sessions)
    if active:
        print(f"Error: session already running for project '{active['project']}'. Stop it first.", file=sys.stderr)
        sys.exit(1)
    now = datetime.now()
    session = {
        "project": args.project,
        "start": now.strftime(DT_FMT),
        "end": None,
        "duration_seconds": None,
    }
    sessions.append(session)
    save_sessions(sessions, args.file)
    print(f"Started tracking '{args.project}' at {now.strftime('%H:%M:%S')}")


def cmd_stop(args: argparse.Namespace) -> None:
    sessions = load_sessions(args.file)
    active = find_active(sessions)
    if not active:
        print("Error: no active session to stop.", file=sys.stderr)
        sys.exit(1)
    now = datetime.now()
    start_dt = datetime.strptime(active["start"], DT_FMT)
    duration = int((now - start_dt).total_seconds())
    active["end"] = now.strftime(DT_FMT)
    active["duration_seconds"] = duration
    save_sessions(sessions, args.file)
    print(f"Stopped '{active['project']}'. Duration: {format_duration(duration)}")


def cmd_status(args: argparse.Namespace) -> None:
    sessions = load_sessions(args.file)
    active = find_active(sessions)
    if not active:
        print("No active session.")
        return
    now = datetime.now()
    start_dt = datetime.strptime(active["start"], DT_FMT)
    elapsed = int((now - start_dt).total_seconds())
    print(f"Active session: '{active['project']}' (started {active['start']}, elapsed {format_duration(elapsed)})")


def cmd_log(args: argparse.Namespace) -> None:
    sessions = load_sessions(args.file)
    if not sessions:
        print("No sessions recorded.")
        return
    print(f"{'Project':<20} {'Start':<20} {'End':<20} {'Duration'}")
    print("-" * 75)
    for s in sessions:
        end = s.get("end") or "(running)"
        dur = format_duration(s["duration_seconds"]) if s.get("duration_seconds") is not None else "(active)"
        print(f"{s['project']:<20} {s['start']:<20} {end:<20} {dur}")


def cmd_report(args: argparse.Namespace) -> None:
    sessions = load_sessions(args.file)
    # Filter by project
    if args.project:
        sessions = [s for s in sessions if s["project"] == args.project]
    # Filter by date
    if args.date:
        sessions = [s for s in sessions if s["start"].startswith(args.date)]
    # Only completed sessions
    completed = [s for s in sessions if s.get("duration_seconds") is not None]
    if not completed:
        print("No completed sessions found for the given filters.")
        return
    # Aggregate by project
    totals: dict = {}
    for s in completed:
        p = s["project"]
        totals[p] = totals.get(p, 0) + s["duration_seconds"]
    print(f"{'Project':<20} {'Total Time'}")
    print("-" * 35)
    grand_total = 0
    for project, secs in sorted(totals.items()):
        print(f"{project:<20} {format_duration(secs)}")
        grand_total += secs
    print("-" * 35)
    print(f"{'TOTAL':<20} {format_duration(grand_total)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Time Tracker CLI")
    parser.add_argument("--file", default=DATA_FILE, help="Sessions file path")
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start tracking a project")
    p_start.add_argument("project", help="Project name")

    sub.add_parser("stop", help="Stop current session")
    sub.add_parser("status", help="Show current active session")
    sub.add_parser("log", help="List all sessions")

    p_report = sub.add_parser("report", help="Show time report")
    p_report.add_argument("--project", help="Filter by project name")
    p_report.add_argument("--date", help="Filter by date (YYYY-MM-DD)")

    args = parser.parse_args()
    if args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
