#!/usr/bin/env python3
"""Priority Job Scheduler CLI (stdlib only). State is stored in scheduler.json."""
import argparse
import heapq
import json
import os
import re
import sys
import tempfile

STATE_FILE = os.environ.get("SCHEDULER_FILE", "scheduler.json")
ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}")
STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")


class SchedulerError(Exception):
    pass


# ---------- persistence ----------

def load():
    """Load jobs (dict id -> job, insertion ordered) and recompute readiness."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
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
            if job["status"] not in STATUSES:
                raise ValueError("bad status %r" % job["status"])
            jobs[job["id"]] = job
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SchedulerError("cannot read %s: %s" % (STATE_FILE, e))
    recompute_ready(jobs)
    return jobs


def save(jobs):
    out = []
    for j in jobs.values():
        j = dict(j)
        if j["status"] == "ready":  # ready is derived, never persisted
            j["status"] = "pending"
        out.append(j)
    d = os.path.dirname(os.path.abspath(STATE_FILE))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".scheduler-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"jobs": out}, f, indent=2)
            f.write("\n")
        os.replace(tmp, STATE_FILE)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def recompute_ready(jobs):
    for j in jobs.values():
        if j["status"] in ("pending", "ready"):
            all_done = all(jobs[d]["status"] == "done" for d in j["depends_on"])
            j["status"] = "ready" if all_done else "pending"


# ---------- graph helpers ----------

def dependents_map(jobs):
    m = {i: [] for i in jobs}
    for j in jobs.values():
        for d in j["depends_on"]:
            if d in m:
                m[d].append(j["id"])
    return m


def has_cycle(jobs):
    indeg = {i: len(set(j["depends_on"])) for i, j in jobs.items()}
    deps = dependents_map(jobs)
    stack = [i for i, n in indeg.items() if n == 0]
    seen = 0
    while stack:
        n = stack.pop()
        seen += 1
        for c in deps[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                stack.append(c)
    return seen != len(jobs)


def execution_order(jobs):
    """Topological order; among available jobs, higher priority first (id breaks ties)."""
    indeg = {i: len(set(j["depends_on"])) for i, j in jobs.items()}
    deps = dependents_map(jobs)
    heap = [(-jobs[i]["priority"], i) for i, n in indeg.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, n = heapq.heappop(heap)
        order.append(n)
        for c in deps[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, (-jobs[c]["priority"], c))
    return order


def cancel_dependents(jobs, root):
    """Cancel all transitive dependents of root; return the cancelled ids."""
    deps = dependents_map(jobs)
    cancelled, stack = [], list(deps[root])
    seen = set()
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        if jobs[n]["status"] in ("pending", "ready"):
            jobs[n]["status"] = "cancelled"
            cancelled.append(n)
        stack.extend(deps[n])
    return sorted(cancelled)


# ---------- commands ----------

def cmd_add(args):
    jobs = load()
    jid = args.id
    if not ID_RE.fullmatch(jid):
        raise SchedulerError("invalid id %r: use 1-32 alphanumeric/underscore chars" % jid)
    if jid in jobs:
        raise SchedulerError("duplicate id %r" % jid)
    if not args.name.strip():
        raise SchedulerError("name must not be empty")
    if not 1 <= args.priority <= 10:
        raise SchedulerError("priority must be between 1 and 10")
    deps = []
    for d in args.depends_on:
        if d not in deps:
            deps.append(d)
    if jid in deps:
        raise SchedulerError("job %r cannot depend on itself" % jid)
    for d in deps:
        if d not in jobs:
            raise SchedulerError("unknown dependency %r" % d)
    jobs[jid] = {"id": jid, "name": args.name, "priority": args.priority,
                 "depends_on": deps, "status": "pending"}
    if has_cycle(jobs):
        raise SchedulerError("adding %r would create a dependency cycle" % jid)
    # a job depending on a failed/cancelled job can never run
    if any(jobs[d]["status"] in ("failed", "cancelled") for d in deps):
        jobs[jid]["status"] = "cancelled"
    recompute_ready(jobs)
    save(jobs)
    print("added %s (%s)" % (jid, jobs[jid]["status"]))


def cmd_run_next(args):
    jobs = load()
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        print("no ready jobs")
        return 1
    order = {i: n for n, i in enumerate(execution_order(jobs))}
    job = min(ready, key=lambda j: (-j["priority"], order[j["id"]]))
    job["status"] = "running"
    save(jobs)
    print("running %s: %s" % (job["id"], job["name"]))
    job["status"] = "done"  # simulated execution
    recompute_ready(jobs)
    save(jobs)
    print("done %s" % job["id"])
    return 0


def cmd_fail(args):
    jobs = load()
    job = jobs.get(args.id)
    if job is None:
        raise SchedulerError("unknown job %r" % args.id)
    if job["status"] in ("done", "failed", "cancelled"):
        raise SchedulerError("job %r is already %s" % (args.id, job["status"]))
    job["status"] = "failed"
    cancelled = cancel_dependents(jobs, args.id)
    recompute_ready(jobs)
    save(jobs)
    print("failed %s" % args.id)
    if cancelled:
        print("cancelled: %s" % ", ".join(cancelled))


def cmd_status(args):
    jobs = load()
    if not jobs:
        print("no jobs")
        return
    print("%-32s %-9s %-4s %s" % ("ID", "STATUS", "PRI", "NAME"))
    for i in execution_order(jobs):
        j = jobs[i]
        print("%-32s %-9s %-4d %s" % (i, j["status"], j["priority"], j["name"]))


def cmd_report(args):
    jobs = load()
    counts = {s: 0 for s in STATUSES}
    for j in jobs.values():
        counts[j["status"]] += 1
    print("Total jobs: %d" % len(jobs))
    for s in STATUSES:
        print("  %-10s %d" % (s, counts[s]))
    order = [i for i in execution_order(jobs) if jobs[i]["status"] in ("pending", "ready", "running")]
    print("Execution order (remaining): %s" % (" -> ".join(order) if order else "(none)"))
    for title, st in (("Failed", "failed"), ("Cancelled", "cancelled")):
        ids = [i for i in jobs if jobs[i]["status"] == st]
        if ids:
            print("%s: %s" % (title, ", ".join(ids)))
    for j in jobs.values():
        if j["status"] in ("pending", "ready"):
            blockers = [d for d in j["depends_on"] if jobs[d]["status"] != "done"]
            if blockers:
                print("  %s waiting on: %s" % (j["id"], ", ".join(blockers)))


def priority_arg(s):
    try:
        return int(s)
    except ValueError:
        raise argparse.ArgumentTypeError("priority must be an integer 1-10")


def main(argv=None):
    p = argparse.ArgumentParser(prog="scheduler.py", description="Priority job scheduler")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("--id", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--priority", type=priority_arg, required=True, help="1-10, higher runs first")
    a.add_argument("--depends-on", nargs="*", default=[], metavar="ID")
    a.set_defaults(func=cmd_add)
    sub.add_parser("run-next", help="run the highest-priority ready job").set_defaults(func=cmd_run_next)
    f = sub.add_parser("fail", help="mark a job failed and cancel its dependents")
    f.add_argument("id")
    f.set_defaults(func=cmd_fail)
    sub.add_parser("status", help="list jobs in execution order").set_defaults(func=cmd_status)
    sub.add_parser("report", help="summary report").set_defaults(func=cmd_report)
    args = p.parse_args(argv)
    try:
        return args.func(args) or 0
    except SchedulerError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
