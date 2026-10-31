#!/usr/bin/env python3
"""Priority Job Scheduler CLI (stdlib only).

Commands: add, run-next, fail <id>, status, report.
State is persisted in scheduler.json (override with --file). The "ready"
status is derived: it is recomputed on load and never written to disk.
"""
import argparse
import heapq
import json
import os
import re
import sys
import tempfile

DEFAULT_FILE = "scheduler.json"
ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}")
STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")
PERSISTED = ("pending", "running", "done", "failed", "cancelled")


class SchedulerError(Exception):
    pass


# ---------------------------------------------------------------- graph logic

def find_cycle(jobs):
    """Return a list of ids forming a cycle, or None."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {i: WHITE for i in jobs}
    for root in jobs:
        if color[root] != WHITE:
            continue
        color[root] = GREY
        path = [root]
        stack = [iter(jobs[root]["depends_on"])]
        while stack:
            for dep in stack[-1]:
                if dep not in jobs:
                    continue
                if color[dep] == GREY:
                    return path[path.index(dep):] + [dep]
                if color[dep] == WHITE:
                    color[dep] = GREY
                    path.append(dep)
                    stack.append(iter(jobs[dep]["depends_on"]))
                    break
            else:
                color[path.pop()] = BLACK
                stack.pop()
    return None


def dependents_map(jobs):
    rev = {i: [] for i in jobs}
    for i, j in jobs.items():
        for d in j["depends_on"]:
            rev[d].append(i)
    return rev


def recompute_ready(jobs):
    """Promote pending jobs whose dependencies are all done to ready."""
    for j in jobs.values():
        if j["status"] == "ready":
            j["status"] = "pending"
    for j in jobs.values():
        if j["status"] == "pending" and all(
            jobs[d]["status"] == "done" for d in j["depends_on"]
        ):
            j["status"] = "ready"


def execution_order(jobs):
    """Topological order; among available jobs, higher priority first.

    Ties on priority are broken by insertion order for determinism.
    """
    seq = {i: n for n, i in enumerate(jobs)}
    indeg = {i: len(set(j["depends_on"])) for i, j in jobs.items()}
    rev = dependents_map(jobs)
    heap = [(-jobs[i]["priority"], seq[i], i) for i, n in indeg.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, _, i = heapq.heappop(heap)
        order.append(i)
        for k in set(rev[i]):
            indeg[k] -= 1
            if indeg[k] == 0:
                heapq.heappush(heap, (-jobs[k]["priority"], seq[k], k))
    return order


def cancel_dependents(jobs, failed_id):
    """Cancel all transitive dependents of failed_id. Returns cancelled ids."""
    rev = dependents_map(jobs)
    cancelled, seen, stack = [], {failed_id}, [failed_id]
    while stack:
        for k in rev[stack.pop()]:
            if k in seen:
                continue
            seen.add(k)
            stack.append(k)
            if jobs[k]["status"] not in ("done", "failed", "cancelled"):
                jobs[k]["status"] = "cancelled"
                cancelled.append(k)
    return cancelled


# ---------------------------------------------------------------- persistence

def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise SchedulerError(f"cannot read {path}: {e}")
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise SchedulerError(f"{path}: invalid format")
    jobs = {}
    for raw in data["jobs"]:
        try:
            jid, name = raw["id"], raw["name"]
            prio, deps = raw["priority"], raw["depends_on"]
            status = raw.get("status", "pending")
        except (KeyError, TypeError):
            raise SchedulerError(f"{path}: malformed job entry")
        if not (isinstance(jid, str) and ID_RE.fullmatch(jid)) or jid in jobs:
            raise SchedulerError(f"{path}: bad or duplicate id {jid!r}")
        if not isinstance(prio, int) or isinstance(prio, bool) or not 1 <= prio <= 10:
            raise SchedulerError(f"{path}: bad priority for {jid}")
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise SchedulerError(f"{path}: bad depends_on for {jid}")
        if status == "ready":  # never trust a persisted ready
            status = "pending"
        if status not in PERSISTED:
            raise SchedulerError(f"{path}: bad status for {jid}")
        jobs[jid] = {"id": jid, "name": str(name), "priority": prio,
                     "depends_on": deps, "status": status}
    for j in jobs.values():
        for d in j["depends_on"]:
            if d not in jobs or d == j["id"]:
                raise SchedulerError(f"{path}: invalid dependency {d!r} in {j['id']}")
    if find_cycle(jobs):
        raise SchedulerError(f"{path}: dependency cycle detected")
    recompute_ready(jobs)
    return jobs


def save(path, jobs):
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


# ------------------------------------------------------------------- commands

def cmd_add(jobs, args):
    jid = args.id
    if not ID_RE.fullmatch(jid):
        raise SchedulerError("id must be 1-32 chars of letters, digits or underscore")
    if jid in jobs:
        raise SchedulerError(f"duplicate id: {jid}")
    if not args.name.strip():
        raise SchedulerError("name must not be empty")
    if not 1 <= args.priority <= 10:
        raise SchedulerError("priority must be between 1 and 10")
    deps = []
    for d in (s.strip() for s in args.depends_on.split(",")):
        if d and d not in deps:
            deps.append(d)
    if jid in deps:
        raise SchedulerError(f"job {jid} cannot depend on itself")
    unknown = [d for d in deps if d not in jobs]
    if unknown:
        raise SchedulerError("unknown dependency: " + ", ".join(unknown))
    jobs[jid] = {"id": jid, "name": args.name, "priority": args.priority,
                 "depends_on": deps, "status": "pending"}
    cycle = find_cycle(jobs)
    if cycle:
        del jobs[jid]
        raise SchedulerError("cycle detected: " + " -> ".join(cycle))
    # A dependency that already failed/was cancelled can never complete.
    if any(jobs[d]["status"] in ("failed", "cancelled") for d in deps):
        jobs[jid]["status"] = "cancelled"
    recompute_ready(jobs)
    print(f"added {jid} ({jobs[jid]['status']})")
    return True


def cmd_run_next(jobs, args):
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        print("no ready jobs")
        return False
    order = {i: n for n, i in enumerate(jobs)}
    job = min(ready, key=lambda j: (-j["priority"], order[j["id"]]))
    job["status"] = "running"
    print(f"running {job['id']} ({job['name']}, priority {job['priority']})")
    # Simulated execution: persist the running state, then complete.
    save(args.file, jobs)
    job["status"] = "done"
    recompute_ready(jobs)
    print(f"done {job['id']}")
    return True


def cmd_fail(jobs, args):
    job = jobs.get(args.job_id)
    if job is None:
        raise SchedulerError(f"unknown job: {args.job_id}")
    if job["status"] in ("done", "failed", "cancelled"):
        raise SchedulerError(f"cannot fail job in status {job['status']}")
    job["status"] = "failed"
    cancelled = cancel_dependents(jobs, job["id"])
    recompute_ready(jobs)
    print(f"failed {job['id']}")
    if cancelled:
        print("cancelled: " + ", ".join(cancelled))
    return True


def cmd_status(jobs, args):
    if not jobs:
        print("no jobs")
        return False
    print(f"{'ID':<32}  {'PRI':>3}  {'STATUS':<9}  DEPENDS_ON")
    for j in jobs.values():
        print(f"{j['id']:<32}  {j['priority']:>3}  {j['status']:<9}  "
              f"{','.join(j['depends_on']) or '-'}")
    return False


def cmd_report(jobs, args):
    counts = {s: 0 for s in STATUSES}
    for j in jobs.values():
        counts[j["status"]] += 1
    print(f"Total jobs: {len(jobs)}")
    for s in STATUSES:
        print(f"  {s:<9} {counts[s]}")
    print("Execution order (remaining):")
    n = 0
    for i in execution_order(jobs):
        j = jobs[i]
        if j["status"] in ("done", "failed", "cancelled"):
            continue
        n += 1
        print(f"  {n}. {i} [{j['status']}, priority {j['priority']}] {j['name']}")
    if n == 0:
        print("  (none)")
    for label in ("failed", "cancelled"):
        ids = [i for i, j in jobs.items() if j["status"] == label]
        if ids:
            print(f"{label.capitalize()}: " + ", ".join(ids))
    return False


def build_parser():
    p = argparse.ArgumentParser(description="Priority job scheduler")
    p.add_argument("--file", default=DEFAULT_FILE, help="state file (default: %(default)s)")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("--id", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--priority", type=int, required=True, help="1-10, higher runs first")
    a.add_argument("--depends-on", default="", help="comma-separated job ids")
    a.set_defaults(func=cmd_add)
    sub.add_parser("run-next", help="run highest-priority ready job").set_defaults(func=cmd_run_next)
    f = sub.add_parser("fail", help="mark a job failed, cancel its dependents")
    f.add_argument("job_id", metavar="id")
    f.set_defaults(func=cmd_fail)
    sub.add_parser("status", help="list jobs").set_defaults(func=cmd_status)
    sub.add_parser("report", help="summary and execution order").set_defaults(func=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        jobs = load(args.file)
        if args.func(jobs, args):
            save(args.file, jobs)
    except SchedulerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
