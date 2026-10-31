#!/usr/bin/env python3
"""Priority Job Scheduler CLI (stdlib only). State is kept in scheduler.json."""
import argparse
import heapq
import json
import os
import re
import sys

STATE_FILE = "scheduler.json"
STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")
TERMINAL = ("done", "failed", "cancelled")
ID_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")


class SchedulerError(Exception):
    pass


# ---------------------------------------------------------------- persistence

def compute_ready(jobs):
    """Recompute ready: a pending job whose depends_on are all done."""
    by_id = {j["id"]: j for j in jobs}
    for j in jobs:
        if j["status"] == "ready":
            j["status"] = "pending"
    for j in jobs:
        if j["status"] == "pending" and all(
            d in by_id and by_id[d]["status"] == "done" for d in j["depends_on"]
        ):
            j["status"] = "ready"


def load(path=None):
    path = path or STATE_FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        jobs = data["jobs"]
        for j in jobs:
            j["id"], j["name"], j["priority"], j["depends_on"], j["status"]
            if j["status"] not in STATUSES:
                raise ValueError(j["status"])
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise SchedulerError("cannot read %s: %s" % (path, exc))
    compute_ready(jobs)
    return jobs


def save(jobs, path=None):
    path = path or STATE_FILE
    out = []
    for j in jobs:
        rec = dict(j)
        if rec["status"] == "ready":  # ready is derived, never persisted
            rec["status"] = "pending"
        out.append(rec)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"jobs": out}, fh, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------------- logic

def would_create_cycle(jobs, new_id, depends_on):
    """True if adding new_id with depends_on closes a cycle in the graph."""
    deps = {j["id"]: j["depends_on"] for j in jobs}
    deps[new_id] = list(depends_on)
    seen, stack = set(), list(depends_on)
    while stack:
        cur = stack.pop()
        if cur == new_id:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(deps.get(cur, []))
    return False


def add_job(jobs, job_id, name, priority, depends_on):
    if not isinstance(job_id, str) or not ID_RE.match(job_id):
        raise SchedulerError("invalid id %r: use 1-32 letters, digits or underscore" % (job_id,))
    if any(j["id"] == job_id for j in jobs):
        raise SchedulerError("duplicate id: %s" % job_id)
    if not isinstance(priority, int) or isinstance(priority, bool) or not 1 <= priority <= 10:
        raise SchedulerError("priority must be an integer from 1 to 10")
    depends_on = list(dict.fromkeys(depends_on))
    if job_id in depends_on:
        raise SchedulerError("self-dependency: %s" % job_id)
    known = {j["id"] for j in jobs}
    for d in depends_on:
        if d not in known:
            raise SchedulerError("unknown dependency: %s" % d)
    if would_create_cycle(jobs, job_id, depends_on):
        raise SchedulerError("dependency cycle detected adding %s" % job_id)
    jobs.append({"id": job_id, "name": name, "priority": priority,
                 "depends_on": depends_on, "status": "pending"})
    compute_ready(jobs)


def execution_order(jobs):
    """Topological order; among available jobs higher priority first, then id."""
    by_id = {j["id"]: j for j in jobs}
    indeg = {j["id"]: len([d for d in set(j["depends_on"]) if d in by_id]) for j in jobs}
    children = {j["id"]: [] for j in jobs}
    for j in jobs:
        for d in set(j["depends_on"]):
            if d in by_id:
                children[d].append(j["id"])
    heap = [(-by_id[i]["priority"], i) for i, n in indeg.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, cur = heapq.heappop(heap)
        order.append(by_id[cur])
        for c in children[cur]:
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, (-by_id[c]["priority"], c))
    return order


def fail_job(jobs, job_id):
    by_id = {j["id"]: j for j in jobs}
    if job_id not in by_id:
        raise SchedulerError("unknown job: %s" % job_id)
    if by_id[job_id]["status"] in TERMINAL:
        raise SchedulerError("job %s is already %s" % (job_id, by_id[job_id]["status"]))
    by_id[job_id]["status"] = "failed"
    cancelled, frontier = [], [job_id]
    while frontier:
        cur = frontier.pop()
        for j in jobs:
            if cur in j["depends_on"] and j["status"] not in ("cancelled", "failed", "done"):
                j["status"] = "cancelled"
                cancelled.append(j["id"])
                frontier.append(j["id"])
    compute_ready(jobs)
    return sorted(cancelled)


def pick_next(jobs):
    ready = [j for j in jobs if j["status"] == "ready"]
    if not ready:
        return None
    return min(ready, key=lambda j: (-j["priority"], j["id"]))


# ------------------------------------------------------------------------ CLI

def fmt(j):
    deps = ",".join(j["depends_on"]) or "-"
    return "%-32s %-9s p=%-2d deps=%s  %s" % (j["id"], j["status"], j["priority"], deps, j["name"])


def build_parser():
    p = argparse.ArgumentParser(prog="scheduler.py", description="Priority job scheduler")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("--id", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--priority", type=int, required=True)
    a.add_argument("--depends-on", default="", help="comma-separated job ids")
    sub.add_parser("run-next", help="run the highest-priority ready job")
    f = sub.add_parser("fail", help="mark a job failed and cancel its dependents")
    f.add_argument("id")
    sub.add_parser("status", help="list jobs and statuses")
    sub.add_parser("report", help="execution order and summary")
    return p


def run(args):
    jobs = load()
    if args.command == "add":
        deps = [d.strip() for d in args.depends_on.split(",") if d.strip()]
        add_job(jobs, args.id, args.name, args.priority, deps)
        save(jobs)
        print("added %s (%s)" % (args.id, next(j for j in jobs if j["id"] == args.id)["status"]))
    elif args.command == "run-next":
        job = pick_next(jobs)
        if job is None:
            print("no ready job")
            return
        job["status"] = "running"
        save(jobs)
        print("running %s" % job["id"])
        job["status"] = "done"  # simulated execution
        compute_ready(jobs)
        save(jobs)
        print("done %s" % job["id"])
    elif args.command == "fail":
        cancelled = fail_job(jobs, args.id)
        save(jobs)
        print("failed %s" % args.id)
        for c in cancelled:
            print("cancelled %s" % c)
    elif args.command == "status":
        for j in jobs:
            print(fmt(j))
    elif args.command == "report":
        print("Execution order:")
        for n, j in enumerate(execution_order(jobs), 1):
            print("%2d. %s" % (n, fmt(j)))
        print("Summary:")
        for s in STATUSES:
            print("  %-9s %d" % (s, sum(1 for j in jobs if j["status"] == s)))


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except SchedulerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
