#!/usr/bin/env python3
"""Priority job scheduler CLI. Standard library only.

State lives in scheduler.json (or $SCHEDULER_FILE). The status "ready" is
derived: it is recomputed on every load and never written to disk.
"""
import argparse
import heapq
import json
import os
import re
import sys

STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")
STORED = ("pending", "running", "done", "failed", "cancelled")
ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}")


class SchedulerError(Exception):
    pass


def state_path():
    return os.environ.get("SCHEDULER_FILE", "scheduler.json")


def valid_id(value):
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def parse_priority(value):
    if isinstance(value, bool):
        raise SchedulerError("priority must be an integer from 1 to 10")
    if isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError:
            raise SchedulerError("priority must be an integer from 1 to 10")
    if not isinstance(value, int) or not 1 <= value <= 10:
        raise SchedulerError("priority must be an integer from 1 to 10")
    return value


def find_cycle(jobs):
    """Return a list of ids forming a cycle, or None."""
    color = {}
    for start in jobs:
        if color.get(start):
            continue
        stack = [(start, iter(jobs[start]["depends_on"]))]
        path = [start]
        color[start] = 1
        while stack:
            node, it = stack[-1]
            for dep in it:
                if dep not in jobs:
                    continue
                if color.get(dep) == 1:
                    return path[path.index(dep):] + [dep]
                if not color.get(dep):
                    color[dep] = 1
                    path.append(dep)
                    stack.append((dep, iter(jobs[dep]["depends_on"])))
                    break
            else:
                color[node] = 2
                path.pop()
                stack.pop()
    return None


def recompute_ready(jobs):
    """Derive ready: pending jobs whose dependencies are all done."""
    for job in jobs.values():
        if job["status"] == "ready":
            job["status"] = "pending"
    for job in jobs.values():
        if job["status"] == "pending" and all(
            jobs[d]["status"] == "done" for d in job["depends_on"]
        ):
            job["status"] = "ready"


def load(path=None):
    path = path or state_path()
    jobs = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            raw = data["jobs"]
            for item in raw:
                job = {
                    "id": item["id"],
                    "name": item["name"],
                    "priority": item["priority"],
                    "depends_on": list(item["depends_on"]),
                    "status": item["status"],
                }
                if not valid_id(job["id"]) or job["id"] in jobs:
                    raise ValueError("bad or duplicate id")
                if job["status"] not in STATUSES:
                    raise ValueError("bad status")
                parse_priority(job["priority"])
                jobs[job["id"]] = job
            for job in jobs.values():
                if any(d not in jobs or d == job["id"] for d in job["depends_on"]):
                    raise ValueError("bad dependency")
        except (OSError, ValueError, KeyError, TypeError, SchedulerError) as exc:
            raise SchedulerError("cannot read %s: %s" % (path, exc))
        if find_cycle(jobs):
            raise SchedulerError("cannot read %s: dependency cycle" % path)
    recompute_ready(jobs)
    return jobs


def save(jobs, path=None):
    path = path or state_path()
    out = []
    for job in jobs.values():
        item = dict(job)
        if item["status"] == "ready":
            item["status"] = "pending"
        out.append(item)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"jobs": out}, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def add_job(jobs, job_id, name, priority, depends_on):
    if not valid_id(job_id):
        raise SchedulerError("invalid id: use 1-32 letters, digits or underscore")
    if job_id in jobs:
        raise SchedulerError("duplicate id: %s" % job_id)
    if not isinstance(name, str) or not name.strip():
        raise SchedulerError("name must not be empty")
    priority = parse_priority(priority)
    deps = list(dict.fromkeys(depends_on or []))
    if job_id in deps:
        raise SchedulerError("job cannot depend on itself: %s" % job_id)
    for dep in deps:
        if dep not in jobs:
            raise SchedulerError("unknown dependency: %s" % dep)
    candidate = dict(jobs)
    candidate[job_id] = {
        "id": job_id, "name": name, "priority": priority,
        "depends_on": deps, "status": "pending",
    }
    cycle = find_cycle(candidate)
    if cycle:
        raise SchedulerError("dependency cycle: " + " -> ".join(cycle))
    jobs[job_id] = candidate[job_id]
    recompute_ready(jobs)
    return jobs[job_id]


def execution_order(jobs):
    """Topological order; among available jobs higher priority first."""
    index = {j: i for i, j in enumerate(jobs)}
    remaining = {j: len(set(jobs[j]["depends_on"])) for j in jobs}
    dependents = {j: [] for j in jobs}
    for j, job in jobs.items():
        for d in set(job["depends_on"]):
            dependents[d].append(j)
    heap = [(-jobs[j]["priority"], index[j], j) for j in jobs if remaining[j] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, _, j = heapq.heappop(heap)
        order.append(j)
        for k in dependents[j]:
            remaining[k] -= 1
            if remaining[k] == 0:
                heapq.heappush(heap, (-jobs[k]["priority"], index[k], k))
    return order


def run_next(jobs):
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        return None
    index = {j: i for i, j in enumerate(jobs)}
    job = min(ready, key=lambda j: (-j["priority"], index[j["id"]]))
    job["status"] = "running"
    job["status"] = "done"  # simulated execution
    recompute_ready(jobs)
    return job


def fail_job(jobs, job_id):
    if job_id not in jobs:
        raise SchedulerError("unknown job: %s" % job_id)
    job = jobs[job_id]
    if job["status"] not in ("pending", "ready", "running"):
        raise SchedulerError("cannot fail job %s with status %s" % (job_id, job["status"]))
    job["status"] = "failed"
    dependents = {j: [] for j in jobs}
    for j, other in jobs.items():
        for d in other["depends_on"]:
            dependents[d].append(j)
    cancelled = []
    stack = list(dependents[job_id])
    seen = set()
    while stack:
        j = stack.pop()
        if j in seen:
            continue
        seen.add(j)
        if jobs[j]["status"] in ("pending", "ready", "running"):
            jobs[j]["status"] = "cancelled"
            cancelled.append(j)
        stack.extend(dependents[j])
    recompute_ready(jobs)
    return sorted(cancelled)


def counts(jobs):
    result = {s: 0 for s in STATUSES}
    for job in jobs.values():
        result[job["status"]] += 1
    return result


def fmt(job):
    deps = ",".join(job["depends_on"]) or "-"
    return "%-32s %-9s p=%-2d deps=%s  %s" % (
        job["id"], job["status"], job["priority"], deps, job["name"])


def build_parser():
    p = argparse.ArgumentParser(prog="scheduler.py", description="Priority job scheduler")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("--id", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--priority", required=True)
    a.add_argument("--depends-on", nargs="*", default=[], metavar="ID")
    sub.add_parser("run-next", help="run the highest-priority ready job")
    f = sub.add_parser("fail", help="fail a job and cancel its dependents")
    f.add_argument("id")
    sub.add_parser("status", help="list jobs and their status")
    sub.add_parser("report", help="execution order and status counts")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        jobs = load()
        if args.command == "add":
            job = add_job(jobs, args.id, args.name, args.priority, args.depends_on)
            save(jobs)
            print("added %s (%s)" % (job["id"], job["status"]))
        elif args.command == "run-next":
            job = run_next(jobs)
            if job is None:
                print("no ready job")
            else:
                save(jobs)
                print("ran %s: running -> done" % job["id"])
        elif args.command == "fail":
            cancelled = fail_job(jobs, args.id)
            save(jobs)
            print("failed %s; cancelled: %s" % (args.id, ", ".join(cancelled) or "none"))
        elif args.command == "status":
            for job in jobs.values():
                print(fmt(job))
        elif args.command == "report":
            print("Execution order:")
            for n, j in enumerate(execution_order(jobs), 1):
                print("  %d. %s" % (n, fmt(jobs[j])))
            print("Counts:")
            for s, n in counts(jobs).items():
                print("  %s: %d" % (s, n))
    except SchedulerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
