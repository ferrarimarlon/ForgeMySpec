#!/usr/bin/env python3
"""Priority Job Scheduler CLI (stdlib only). State is kept in scheduler.json."""
import argparse
import heapq
import json
import os
import re
import sys
import tempfile

DB_FILE = "scheduler.json"
ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}")
STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")


class SchedulerError(Exception):
    pass


# ---------- persistence ----------

def load(path=DB_FILE):
    """Load jobs (insertion-ordered dict) and recompute ready status."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        jobs = {}
        for j in data["jobs"]:
            job = {
                "id": j["id"],
                "name": j["name"],
                "priority": j["priority"],
                "depends_on": list(j["depends_on"]),
                "status": j["status"],
            }
            if (not isinstance(job["id"], str) or not ID_RE.fullmatch(job["id"])
                    or job["id"] in jobs
                    or not isinstance(job["priority"], int)
                    or isinstance(job["priority"], bool)
                    or not 1 <= job["priority"] <= 10
                    or job["status"] not in STATUSES):
                raise ValueError("invalid job record")
            jobs[job["id"]] = job
        for job in jobs.values():
            if any(d not in jobs or d == job["id"] for d in job["depends_on"]):
                raise ValueError("invalid dependency")
        if find_cycle(jobs):
            raise ValueError("dependency cycle")
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SchedulerError(f"cannot read {path}: {e}")
    recompute_ready(jobs)
    return jobs


def save(jobs, path=DB_FILE):
    """Atomically write state; 'ready' is never persisted (stored as pending)."""
    out = []
    for j in jobs.values():
        rec = dict(j)
        if rec["status"] == "ready":
            rec["status"] = "pending"
        out.append(rec)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".scheduler-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"jobs": out}, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ---------- graph logic ----------

def recompute_ready(jobs):
    for j in jobs.values():
        if j["status"] in ("pending", "ready"):
            all_done = all(jobs[d]["status"] == "done" for d in j["depends_on"])
            j["status"] = "ready" if all_done else "pending"


def find_cycle(jobs):
    """Return True if the dependency graph contains a cycle (iterative DFS)."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {i: WHITE for i in jobs}
    for root in jobs:
        if color[root] != WHITE:
            continue
        color[root] = GREY
        stack = [(root, iter(jobs[root]["depends_on"]))]
        while stack:
            node, it = stack[-1]
            for dep in it:
                if dep not in jobs:
                    continue
                if color[dep] == GREY:
                    return True
                if color[dep] == WHITE:
                    color[dep] = GREY
                    stack.append((dep, iter(jobs[dep]["depends_on"])))
                    break
            else:
                color[node] = BLACK
                stack.pop()
    return False


def dependents_map(jobs):
    rev = {i: [] for i in jobs}
    for j in jobs.values():
        for d in j["depends_on"]:
            rev[d].append(j["id"])
    return rev


def execution_order(jobs):
    """Topological order; among available jobs higher priority first, then insertion order."""
    index = {i: n for n, i in enumerate(jobs)}
    rev = dependents_map(jobs)
    indeg = {i: len(set(j["depends_on"])) for i, j in jobs.items()}
    heap = [(-j["priority"], index[i], i) for i, j in jobs.items() if indeg[i] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, _, i = heapq.heappop(heap)
        order.append(i)
        for k in rev[i]:
            indeg[k] -= 1
            if indeg[k] == 0:
                heapq.heappush(heap, (-jobs[k]["priority"], index[k], k))
    return order


# ---------- commands ----------

def parse_deps(values):
    deps = []
    for v in values or []:
        for part in v.split(","):
            part = part.strip()
            if part and part not in deps:
                deps.append(part)
    return deps


def cmd_add(args):
    jobs = load()
    jid = args.id
    if not ID_RE.fullmatch(jid):
        raise SchedulerError("invalid id: use 1-32 alphanumeric/underscore characters")
    if jid in jobs:
        raise SchedulerError(f"duplicate id: {jid}")
    if not 1 <= args.priority <= 10:
        raise SchedulerError("priority must be between 1 and 10")
    if not args.name.strip():
        raise SchedulerError("name must not be empty")
    deps = parse_deps(args.depends_on)
    if jid in deps:
        raise SchedulerError(f"self-dependency: {jid} cannot depend on itself")
    unknown = [d for d in deps if d not in jobs]
    if unknown:
        raise SchedulerError("unknown dependency: " + ", ".join(unknown))
    job = {"id": jid, "name": args.name, "priority": args.priority,
           "depends_on": deps, "status": "pending"}
    trial = dict(jobs)
    trial[jid] = job
    if find_cycle(trial):
        raise SchedulerError(f"adding {jid} would create a dependency cycle")
    # A job depending on a failed/cancelled job can never run.
    if any(jobs[d]["status"] in ("failed", "cancelled") for d in deps):
        job["status"] = "cancelled"
    trial[jid] = job
    recompute_ready(trial)
    save(trial)
    print(f"added {jid} [{job['status']}]")


def cmd_run_next(args):
    jobs = load()
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        print("no ready jobs")
        return 1
    index = {i: n for n, i in enumerate(jobs)}
    job = min(ready, key=lambda j: (-j["priority"], index[j["id"]]))
    job["status"] = "running"
    save(jobs)
    print(f"running {job['id']} ({job['name']}, priority {job['priority']})")
    job["status"] = "done"  # simulated execution
    recompute_ready(jobs)
    save(jobs)
    print(f"done {job['id']}")
    return 0


def cmd_fail(args):
    jobs = load()
    job = jobs.get(args.id)
    if job is None:
        raise SchedulerError(f"unknown job: {args.id}")
    if job["status"] not in ("pending", "ready", "running"):
        raise SchedulerError(f"cannot fail {args.id}: status is {job['status']}")
    job["status"] = "failed"
    rev = dependents_map(jobs)
    cancelled = []
    stack = list(rev[args.id])
    seen = set()
    while stack:
        i = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        if jobs[i]["status"] in ("pending", "ready"):
            jobs[i]["status"] = "cancelled"
            cancelled.append(i)
        stack.extend(rev[i])
    recompute_ready(jobs)
    save(jobs)
    print(f"failed {args.id}")
    for i in sorted(cancelled, key=list(jobs).index):
        print(f"cancelled {i}")
    return 0


def fmt(j):
    deps = ",".join(j["depends_on"]) or "-"
    return f"{j['id']:<32} {j['status']:<10} p{j['priority']:<3} deps={deps}  {j['name']}"


def cmd_status(args):
    jobs = load()
    if not jobs:
        print("no jobs")
        return 0
    for j in jobs.values():
        print(fmt(j))
    return 0


def cmd_report(args):
    jobs = load()
    counts = {s: 0 for s in STATUSES}
    for j in jobs.values():
        counts[j["status"]] += 1
    print(f"Total jobs: {len(jobs)}")
    for s in STATUSES:
        print(f"  {s:<10} {counts[s]}")
    print("Execution order:")
    order = execution_order(jobs)
    if not order:
        print("  (none)")
    for n, i in enumerate(order, 1):
        j = jobs[i]
        print(f"  {n}. {i} (p{j['priority']}, {j['status']})")
    for s in ("failed", "cancelled"):
        ids = [i for i, j in jobs.items() if j["status"] == s]
        if ids:
            print(f"{s.capitalize()}: {', '.join(ids)}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Priority job scheduler")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("--id", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--priority", type=int, default=5, help="1-10, higher runs first")
    a.add_argument("--depends-on", nargs="*", default=[], metavar="ID",
                   help="dependency ids (space or comma separated)")
    a.set_defaults(func=cmd_add)
    sub.add_parser("run-next", help="run highest-priority ready job").set_defaults(func=cmd_run_next)
    f = sub.add_parser("fail", help="mark a job failed and cancel its dependents")
    f.add_argument("id")
    f.set_defaults(func=cmd_fail)
    sub.add_parser("status", help="list jobs").set_defaults(func=cmd_status)
    sub.add_parser("report", help="summary and execution order").set_defaults(func=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except SchedulerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
