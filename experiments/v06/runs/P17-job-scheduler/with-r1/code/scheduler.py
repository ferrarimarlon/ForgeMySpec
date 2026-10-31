#!/usr/bin/env python3
"""Priority job scheduler CLI. Single file, stdlib only. State lives in scheduler.json."""
import argparse
import heapq
import json
import os
import re
import sys

STATE_FILE = "scheduler.json"
STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")
PERSISTED = ("pending", "running", "done", "failed", "cancelled")  # "ready" is derived
ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}", re.ASCII)


class SchedulerError(Exception):
    pass


# ---------------------------------------------------------------- core logic

def validate_new_job(jobs, job_id, name, priority, depends_on):
    if not isinstance(job_id, str) or not ID_RE.fullmatch(job_id):
        raise SchedulerError("invalid id %r: use 1-32 letters, digits or underscore" % (job_id,))
    if not isinstance(name, str) or not name.strip():
        raise SchedulerError("name must be a non-empty string")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 10:
        raise SchedulerError("priority must be an integer from 1 to 10")
    if any(j["id"] == job_id for j in jobs):
        raise SchedulerError("duplicate id %r" % job_id)
    if job_id in depends_on:
        raise SchedulerError("job %r cannot depend on itself" % job_id)
    known = {j["id"] for j in jobs}
    for dep in depends_on:
        if dep not in known:
            raise SchedulerError("unknown dependency %r" % dep)
    if find_cycle(jobs, job_id, depends_on):
        raise SchedulerError("adding %r would create a dependency cycle" % job_id)


def find_cycle(jobs, new_id, new_deps):
    """True if the graph plus a job new_id -> new_deps contains a cycle through new_id."""
    deps = {j["id"]: list(j["depends_on"]) for j in jobs}
    deps[new_id] = list(new_deps)
    seen = set()
    stack = list(new_deps)
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
    depends_on = list(dict.fromkeys(depends_on))
    validate_new_job(jobs, job_id, name, priority, depends_on)
    job = {"id": job_id, "name": name, "priority": priority,
           "depends_on": depends_on, "status": "pending"}
    jobs.append(job)
    return job


def recompute_ready(jobs):
    """Derive 'ready' from pending jobs whose dependencies are all done."""
    by_id = {j["id"]: j for j in jobs}
    for j in jobs:
        if j["status"] in ("pending", "ready"):
            ok = all(d in by_id and by_id[d]["status"] == "done" for d in j["depends_on"])
            j["status"] = "ready" if ok else "pending"


def execution_order(jobs):
    """Topological order; among available jobs higher priority first, then id ascending."""
    by_id = {j["id"]: j for j in jobs}
    indeg = {j["id"]: sum(1 for d in set(j["depends_on"]) if d in by_id) for j in jobs}
    dependents = {j["id"]: [] for j in jobs}
    for j in jobs:
        for d in set(j["depends_on"]):
            if d in by_id:
                dependents[d].append(j["id"])
    heap = [(-by_id[i]["priority"], i) for i, n in indeg.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, cur = heapq.heappop(heap)
        order.append(by_id[cur])
        for nxt in dependents[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(heap, (-by_id[nxt]["priority"], nxt))
    return order


def pick_next(jobs):
    ready = [j for j in jobs if j["status"] == "ready"]
    if not ready:
        return None
    return min(ready, key=lambda j: (-j["priority"], j["id"]))


def fail_job(jobs, job_id):
    by_id = {j["id"]: j for j in jobs}
    job = by_id.get(job_id)
    if job is None:
        raise SchedulerError("unknown job %r" % job_id)
    if job["status"] not in ("pending", "ready"):
        raise SchedulerError("job %r is %s; only pending or ready jobs can fail" % (job_id, job["status"]))
    job["status"] = "failed"
    cancelled = []
    changed = True
    doomed = {job_id}
    while changed:
        changed = False
        for j in jobs:
            if j["id"] not in doomed and any(d in doomed for d in j["depends_on"]):
                doomed.add(j["id"])
                changed = True
    for j in jobs:
        if j["id"] in doomed and j["id"] != job_id and j["status"] not in ("done", "failed", "cancelled"):
            j["status"] = "cancelled"
            cancelled.append(j["id"])
    return sorted(cancelled)


# --------------------------------------------------------------- persistence

def load(path=STATE_FILE):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        raise SchedulerError("cannot read %s: %s" % (path, exc))
    try:
        jobs = data["jobs"]
        for j in jobs:
            j["id"], j["name"], j["priority"], j["depends_on"], j["status"]
            if j["status"] not in STATUSES:
                raise ValueError("bad status %r" % j["status"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SchedulerError("malformed %s: %s" % (path, exc))
    recompute_ready(jobs)
    return jobs


def save(jobs, path=STATE_FILE):
    out = []
    for j in jobs:
        copy = dict(j)
        if copy["status"] == "ready":
            copy["status"] = "pending"
        out.append(copy)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"jobs": out}, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


# ------------------------------------------------------------------- the CLI

def _fmt(j):
    deps = ",".join(j["depends_on"]) or "-"
    return "%-32s %-9s p=%-2d deps=%s  %s" % (j["id"], j["status"], j["priority"], deps, j["name"])


def cmd_add(args):
    jobs = load()
    try:
        priority = int(args.priority)
    except ValueError:
        raise SchedulerError("priority must be an integer from 1 to 10")
    deps = [d for d in (args.depends_on or "").split(",") if d != ""]
    add_job(jobs, args.id, args.name, priority, deps)
    recompute_ready(jobs)
    save(jobs)
    print("added %s" % args.id)


def cmd_run_next(args):
    jobs = load()
    job = pick_next(jobs)
    if job is None:
        print("no ready job")
        return
    job["status"] = "running"
    save(jobs)
    print("running %s" % job["id"])
    job["status"] = "done"  # simulated work
    save(jobs)
    print("done %s" % job["id"])


def cmd_fail(args):
    jobs = load()
    cancelled = fail_job(jobs, args.id)
    recompute_ready(jobs)
    save(jobs)
    print("failed %s" % args.id)
    for c in cancelled:
        print("cancelled %s" % c)


def cmd_status(args):
    for j in load():
        print(_fmt(j))


def cmd_report(args):
    jobs = load()
    print("Execution order:")
    for i, j in enumerate(execution_order(jobs), 1):
        print("%3d. %s" % (i, _fmt(j)))
    print("Summary:")
    for s in STATUSES:
        print("  %-9s %d" % (s, sum(1 for j in jobs if j["status"] == s)))
    print("  total     %d" % len(jobs))


def build_parser():
    p = argparse.ArgumentParser(prog="scheduler.py", description="Priority job scheduler")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("--id", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--priority", required=True)
    a.add_argument("--depends-on", default="", help="comma separated job ids")
    a.set_defaults(func=cmd_add)
    sub.add_parser("run-next", help="run the highest-priority ready job").set_defaults(func=cmd_run_next)
    f = sub.add_parser("fail", help="mark a job failed and cancel its dependents")
    f.add_argument("id")
    f.set_defaults(func=cmd_fail)
    sub.add_parser("status", help="list jobs").set_defaults(func=cmd_status)
    sub.add_parser("report", help="execution order and summary").set_defaults(func=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SchedulerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
