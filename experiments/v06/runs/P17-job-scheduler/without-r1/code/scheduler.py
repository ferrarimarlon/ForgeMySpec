#!/usr/bin/env python3
"""Priority Job Scheduler CLI (stdlib only).

Usage:
  scheduler.py add <id> <name> [-p PRIORITY] [-d DEP[,DEP...]]
  scheduler.py run-next
  scheduler.py fail <id>
  scheduler.py status
  scheduler.py report

State is stored in scheduler.json (override with --file or $SCHEDULER_FILE).
"ready" is derived from the other statuses and is never written to disk.
"""
import argparse
import heapq
import json
import os
import re
import sys
import tempfile

STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")
PERSISTED = ("pending", "running", "done", "failed", "cancelled")
ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}")
DEFAULT_FILE = "scheduler.json"


class SchedulerError(Exception):
    pass


# ---------------------------------------------------------------- validation

def valid_id(value):
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def valid_priority(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 10


def find_cycle(jobs):
    """Return a list of ids forming a cycle, or None. Iterative DFS."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {i: WHITE for i in jobs}
    for root in sorted(jobs):
        if color[root] != WHITE:
            continue
        stack = [(root, iter(jobs[root]["depends_on"]))]
        path = [root]
        color[root] = GREY
        while stack:
            node, it = stack[-1]
            for dep in it:
                if dep not in jobs:
                    continue
                if color[dep] == GREY:
                    return path[path.index(dep):] + [dep]
                if color[dep] == WHITE:
                    color[dep] = GREY
                    path.append(dep)
                    stack.append((dep, iter(jobs[dep]["depends_on"])))
                    break
            else:
                color[node] = BLACK
                path.pop()
                stack.pop()
    return None


# ------------------------------------------------------------------ storage

def load(path):
    """Load jobs (insertion-ordered dict) and recompute ready."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise SchedulerError(f"cannot read {path}: {e}")
    raw = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise SchedulerError(f"{path}: expected an object with a 'jobs' list")
    jobs = {}
    for j in raw:
        if not isinstance(j, dict):
            raise SchedulerError(f"{path}: malformed job entry")
        jid = j.get("id")
        deps = j.get("depends_on", [])
        status = j.get("status", "pending")
        if not valid_id(jid):
            raise SchedulerError(f"{path}: invalid job id {jid!r}")
        if jid in jobs:
            raise SchedulerError(f"{path}: duplicate job id {jid!r}")
        if not isinstance(j.get("name"), str):
            raise SchedulerError(f"{path}: job {jid!r} has invalid name")
        if not valid_priority(j.get("priority")):
            raise SchedulerError(f"{path}: job {jid!r} has invalid priority")
        if not isinstance(deps, list) or not all(valid_id(d) for d in deps):
            raise SchedulerError(f"{path}: job {jid!r} has invalid depends_on")
        if status == "ready":  # tolerate, but ready is always recomputed
            status = "pending"
        if status not in PERSISTED:
            raise SchedulerError(f"{path}: job {jid!r} has invalid status {status!r}")
        jobs[jid] = {"id": jid, "name": j["name"], "priority": j["priority"],
                     "depends_on": list(dict.fromkeys(deps)), "status": status}
    for j in jobs.values():
        for d in j["depends_on"]:
            if d not in jobs:
                raise SchedulerError(f"{path}: job {j['id']!r} depends on unknown job {d!r}")
            if d == j["id"]:
                raise SchedulerError(f"{path}: job {j['id']!r} depends on itself")
    cycle = find_cycle(jobs)
    if cycle:
        raise SchedulerError(f"{path}: dependency cycle: {' -> '.join(cycle)}")
    refresh_ready(jobs)
    return jobs


def save(path, jobs):
    out = []
    for j in jobs.values():
        rec = dict(j)
        if rec["status"] == "ready":
            rec["status"] = "pending"
        out.append(rec)
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".scheduler-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"jobs": out}, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# -------------------------------------------------------------------- logic

def refresh_ready(jobs):
    """Recompute pending <-> ready from dependency state."""
    for j in jobs.values():
        if j["status"] in ("pending", "ready"):
            ok = all(jobs[d]["status"] == "done" for d in j["depends_on"])
            j["status"] = "ready" if ok else "pending"


def dependents_map(jobs):
    rev = {i: [] for i in jobs}
    for j in jobs.values():
        for d in j["depends_on"]:
            rev[d].append(j["id"])
    return rev


def execution_order(jobs):
    """Topological order; among available jobs, higher priority first (ties by id)."""
    indeg = {i: len(set(j["depends_on"])) for i, j in jobs.items()}
    rev = dependents_map(jobs)
    heap = [(-j["priority"], i) for i, j in jobs.items() if indeg[i] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, i = heapq.heappop(heap)
        order.append(i)
        for k in rev[i]:
            indeg[k] -= 1
            if indeg[k] == 0:
                heapq.heappush(heap, (-jobs[k]["priority"], k))
    return order


def add_job(jobs, jid, name, priority, deps):
    if not valid_id(jid):
        raise SchedulerError("invalid id: use 1-32 alphanumeric/underscore characters")
    if jid in jobs:
        raise SchedulerError(f"duplicate id: {jid}")
    if not isinstance(name, str) or not name.strip():
        raise SchedulerError("name must be non-empty")
    if not valid_priority(priority):
        raise SchedulerError("priority must be an integer from 1 to 10")
    deps = list(dict.fromkeys(deps))
    for d in deps:
        if d == jid:
            raise SchedulerError(f"self-dependency: {jid}")
    for d in deps:
        if not valid_id(d):
            raise SchedulerError(f"invalid dependency id: {d!r}")
        if d not in jobs:
            raise SchedulerError(f"unknown dependency: {d}")
    new = {"id": jid, "name": name, "priority": priority,
           "depends_on": deps, "status": "pending"}
    trial = dict(jobs)
    trial[jid] = new
    cycle = find_cycle(trial)
    if cycle:
        raise SchedulerError(f"cycle detected: {' -> '.join(cycle)}")
    # A job depending on a failed/cancelled job can never run.
    if any(jobs[d]["status"] in ("failed", "cancelled") for d in deps):
        new["status"] = "cancelled"
    jobs[jid] = new
    refresh_ready(jobs)
    return new


def fail_job(jobs, jid):
    if jid not in jobs:
        raise SchedulerError(f"unknown job: {jid}")
    job = jobs[jid]
    if job["status"] not in ("pending", "ready", "running"):
        raise SchedulerError(f"cannot fail job {jid}: status is {job['status']}")
    job["status"] = "failed"
    rev = dependents_map(jobs)
    cancelled, stack = [], list(rev[jid])
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
    refresh_ready(jobs)
    order = {i: n for n, i in enumerate(execution_order(jobs))}
    return sorted(cancelled, key=order.get)


def pick_next(jobs):
    order = execution_order(jobs)
    pos = {i: n for n, i in enumerate(order)}
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        return None
    return min(ready, key=lambda j: (-j["priority"], pos[j["id"]]))


# ----------------------------------------------------------------- commands

def fmt(j):
    deps = ",".join(j["depends_on"]) or "-"
    return f"{j['id']:<32}  {j['status']:<9}  p{j['priority']:<2}  {j['name']}  [deps: {deps}]"


def cmd_add(a, jobs):
    deps = []
    for chunk in a.depends_on or []:
        deps.extend(s.strip() for s in chunk.split(",") if s.strip())
    j = add_job(jobs, a.id, a.name, a.priority, deps)
    print(f"added {j['id']} ({j['status']})")
    return True


def cmd_run_next(a, jobs):
    j = pick_next(jobs)
    if j is None:
        print("no ready jobs")
        return False
    j["status"] = "running"
    save(a.file, jobs)  # persist the running state before "executing"
    print(f"running {j['id']}: {j['name']} (priority {j['priority']})")
    j["status"] = "done"
    refresh_ready(jobs)
    print(f"done {j['id']}")
    return True


def cmd_fail(a, jobs):
    cancelled = fail_job(jobs, a.id)
    print(f"failed {a.id}")
    if cancelled:
        print("cancelled: " + ", ".join(cancelled))
    return True


def cmd_status(a, jobs):
    if not jobs:
        print("no jobs")
        return False
    for i in execution_order(jobs):
        print(fmt(jobs[i]))
    return False


def cmd_report(a, jobs):
    counts = {s: 0 for s in STATUSES}
    for j in jobs.values():
        counts[j["status"]] += 1
    print(f"total jobs: {len(jobs)}")
    for s in STATUSES:
        print(f"  {s:<9} {counts[s]}")
    order = execution_order(jobs)
    for title, status in (("Failed", "failed"), ("Cancelled", "cancelled")):
        items = [i for i in order if jobs[i]["status"] == status]
        if items:
            print(f"{title}: " + ", ".join(items))
    queue = [i for i in order if jobs[i]["status"] in ("ready", "pending", "running")]
    if queue:
        print("Execution order (remaining):")
        for n, i in enumerate(queue, 1):
            print(f"  {n}. {fmt(jobs[i])}")
    return False


def build_parser():
    p = argparse.ArgumentParser(prog="scheduler.py", description="Priority job scheduler")
    p.add_argument("--file", default=os.environ.get("SCHEDULER_FILE", DEFAULT_FILE),
                   help="state file (default: scheduler.json)")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("add", help="add a job")
    s.add_argument("id")
    s.add_argument("name")
    s.add_argument("-p", "--priority", type=int, default=5, help="1-10 (default 5)")
    s.add_argument("-d", "--depends-on", action="append", metavar="IDS",
                   help="comma-separated dependency ids (repeatable)")
    s.set_defaults(func=cmd_add)
    s = sub.add_parser("run-next", help="run the highest-priority ready job")
    s.set_defaults(func=cmd_run_next)
    s = sub.add_parser("fail", help="mark a job failed and cancel its dependents")
    s.add_argument("id")
    s.set_defaults(func=cmd_fail)
    s = sub.add_parser("status", help="list jobs in execution order")
    s.set_defaults(func=cmd_status)
    s = sub.add_parser("report", help="summary report")
    s.set_defaults(func=cmd_report)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        jobs = load(args.file)
        if args.func(args, jobs):
            save(args.file, jobs)
    except SchedulerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
