#!/usr/bin/env python3
"""CLI Job Scheduler — single-file implementation using Python stdlib only."""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_FILE = Path(__file__).parent / "scheduler.json"
VALID_STATUSES = {"pending", "ready", "running", "done", "failed", "cancelled"}
ID_MAX_LEN = 32


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_jobs(path: Path = DATA_FILE) -> dict:
    if path.exists():
        with path.open() as fh:
            jobs = json.load(fh)
    else:
        jobs = {}
    recompute_ready(jobs)
    return jobs


def save_jobs(jobs: dict, path: Path = DATA_FILE) -> None:
    with path.open("w") as fh:
        json.dump(jobs, fh, indent=2)


# ---------------------------------------------------------------------------
# Business logic helpers
# ---------------------------------------------------------------------------

def recompute_ready(jobs: dict) -> None:
    """Set status=ready for jobs whose deps are all done, else revert to pending."""
    for job_id, job in jobs.items():
        if job["status"] not in ("pending", "ready"):
            continue
        deps_done = all(
            jobs[dep]["status"] == "done"
            for dep in job["depends_on"]
            if dep in jobs
        )
        job["status"] = "ready" if deps_done else "pending"


def _id_valid(job_id: str) -> bool:
    import re
    return bool(re.match(r"^[A-Za-z0-9_]{1,32}$", job_id))


def _has_cycle(jobs: dict, new_id: str, depends_on: list) -> bool:
    """DFS: starting from new_id's dependencies, check if new_id is reachable."""
    visited = set()
    stack = list(depends_on)
    while stack:
        node = stack.pop()
        if node == new_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        if node in jobs:
            stack.extend(jobs[node]["depends_on"])
    return False


def _topological_sort(jobs: dict) -> list:
    """Return job ids in topological order; ties broken by priority descending."""
    in_degree = defaultdict(int)
    dependents_map = defaultdict(list)  # dep -> [jobs that depend on dep]

    for job_id, job in jobs.items():
        in_degree.setdefault(job_id, 0)
        for dep in job["depends_on"]:
            dependents_map[dep].append(job_id)
            in_degree[job_id] += 0  # ensure key exists

    # count real in-degrees
    for job_id in jobs:
        in_degree[job_id] = sum(
            1 for dep in jobs[job_id]["depends_on"] if dep in jobs
        )

    # collect nodes with in_degree == 0, sorted by priority desc
    queue = sorted(
        [jid for jid, deg in in_degree.items() if deg == 0],
        key=lambda jid: jobs[jid]["priority"],
        reverse=True,
    )

    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        # reduce in-degree of dependents, add newly zero ones (sorted by priority)
        newly_free = []
        for dependent in dependents_map[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                newly_free.append(dependent)
        # insert newly free nodes in priority order (merge into queue)
        if newly_free:
            newly_free_sorted = sorted(
                newly_free,
                key=lambda jid: jobs[jid]["priority"],
                reverse=True,
            )
            # merge: keep queue sorted by priority desc
            merged = queue + newly_free_sorted
            merged.sort(key=lambda jid: jobs[jid]["priority"], reverse=True)
            queue = merged

    return result


def _cancel_downstream(jobs: dict, failed_id: str) -> list:
    """Recursively cancel all transitive dependents of failed_id."""
    # Build reverse dependency map: job_id -> list of jobs that depend on it
    dependents_map = defaultdict(list)
    for job_id, job in jobs.items():
        for dep in job["depends_on"]:
            dependents_map[dep].append(job_id)

    cancelled = []
    stack = list(dependents_map[failed_id])
    visited = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        if jobs[node]["status"] not in ("done", "failed"):
            jobs[node]["status"] = "cancelled"
            cancelled.append(node)
        stack.extend(dependents_map[node])
    return cancelled


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args, jobs: dict) -> int:
    job_id = args.id
    name = args.name
    priority = args.priority
    depends_on = args.depends_on or []

    # Validate id format
    if not _id_valid(job_id):
        print(
            f"Error: id '{job_id}' is invalid. Must be alphanumeric/underscore, 1–32 chars.",
            file=sys.stderr,
        )
        return 1

    # Reject duplicate id
    if job_id in jobs:
        print(f"Error: job id '{job_id}' already exists.", file=sys.stderr)
        return 1

    # Validate priority range
    if not (1 <= priority <= 10):
        print("Error: priority must be between 1 and 10.", file=sys.stderr)
        return 1

    # Reject self-dependency
    if job_id in depends_on:
        print(f"Error: job '{job_id}' cannot depend on itself.", file=sys.stderr)
        return 1

    # Reject unknown dependencies
    unknown = [dep for dep in depends_on if dep not in jobs]
    if unknown:
        print(
            f"Error: unknown job id(s) in depends_on: {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 1

    # Cycle detection
    if _has_cycle(jobs, job_id, depends_on):
        print(
            f"Error: adding '{job_id}' would create a circular dependency.",
            file=sys.stderr,
        )
        return 1

    # Determine initial status
    deps_done = all(jobs[dep]["status"] == "done" for dep in depends_on)
    status = "ready" if deps_done else "pending"

    jobs[job_id] = {
        "id": job_id,
        "name": name,
        "priority": priority,
        "depends_on": depends_on,
        "status": status,
    }
    save_jobs(jobs)
    print(f"Added job '{job_id}' (status={status}).")
    return 0


def cmd_run_next(args, jobs: dict) -> int:
    ready_jobs = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready_jobs:
        print("No jobs ready")
        return 0

    # Pick highest-priority ready job
    best = max(ready_jobs, key=lambda j: j["priority"])
    job_id = best["id"]

    jobs[job_id]["status"] = "running"
    print(f"Running job '{job_id}' ({best['name']}, priority={best['priority']})...")
    jobs[job_id]["status"] = "done"
    print(f"Job '{job_id}' completed (status=done).")

    recompute_ready(jobs)
    save_jobs(jobs)
    return 0


def cmd_fail(args, jobs: dict) -> int:
    job_id = args.job_id
    if job_id not in jobs:
        print(f"Error: job '{job_id}' not found.", file=sys.stderr)
        return 1

    current = jobs[job_id]["status"]
    if current in ("done", "cancelled"):
        print(
            f"Error: cannot fail job '{job_id}' with status '{current}'.",
            file=sys.stderr,
        )
        return 1

    jobs[job_id]["status"] = "failed"
    cancelled = _cancel_downstream(jobs, job_id)
    save_jobs(jobs)
    print(f"Job '{job_id}' marked as failed.")
    if cancelled:
        print(f"Cancelled downstream jobs: {', '.join(cancelled)}")
    return 0


def cmd_status(args, jobs: dict) -> int:
    if not jobs:
        print("No jobs registered.")
        return 0

    ordered = _topological_sort(jobs)
    # Header
    col_id = max(len("ID"), max(len(jid) for jid in jobs))
    col_name = max(len("NAME"), max(len(j["name"]) for j in jobs.values()))
    col_pri = len("PRIORITY")
    col_status = max(len("STATUS"), max(len(j["status"]) for j in jobs.values()))
    col_deps = len("DEPENDS_ON")

    fmt = f"{{:<{col_id}}}  {{:<{col_name}}}  {{:<{col_pri}}}  {{:<{col_status}}}  {{}}"
    header = fmt.format("ID", "NAME", "PRIORITY", "STATUS", "DEPENDS_ON")
    separator = "-" * len(header)
    print(header)
    print(separator)
    for jid in ordered:
        j = jobs[jid]
        deps_str = ", ".join(j["depends_on"]) if j["depends_on"] else "(none)"
        print(fmt.format(jid, j["name"], j["priority"], j["status"], deps_str))
    return 0


def cmd_report(args, jobs: dict) -> int:
    counts = {s: 0 for s in VALID_STATUSES}
    for j in jobs.values():
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    print("Status Report")
    print("-------------")
    for status in ("pending", "ready", "running", "done", "failed", "cancelled"):
        print(f"  {status:<12}: {counts[status]}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scheduler",
        description="CLI Job Scheduler",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a new job")
    p_add.add_argument("--id", required=True, dest="id", help="Job id")
    p_add.add_argument("--name", required=True, help="Job name")
    p_add.add_argument(
        "--priority", required=True, type=int, help="Priority 1–10 (higher = more urgent)"
    )
    p_add.add_argument(
        "--depends-on", dest="depends_on", nargs="*", default=[], metavar="ID",
        help="Job ids this job depends on",
    )

    # run-next
    sub.add_parser("run-next", help="Run the next highest-priority ready job")

    # fail
    p_fail = sub.add_parser("fail", help="Mark a job as failed")
    p_fail.add_argument("job_id", metavar="<id>", help="Job id to fail")

    # status
    sub.add_parser("status", help="Show status table of all jobs")

    # report
    sub.add_parser("report", help="Show count per status")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    jobs = load_jobs()

    dispatch = {
        "add": cmd_add,
        "run-next": cmd_run_next,
        "fail": cmd_fail,
        "status": cmd_status,
        "report": cmd_report,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    return handler(args, jobs)


if __name__ == "__main__":
    sys.exit(main())
