#!/usr/bin/env python3
"""Priority Job Scheduler CLI (stdlib only). State is kept in scheduler.json."""
import argparse
import heapq
import json
import os
import re
import sys
import tempfile

ID_RE = re.compile(r"[A-Za-z0-9_]{1,32}")
STATUSES = ("pending", "ready", "running", "done", "failed", "cancelled")
TERMINAL = ("done", "failed", "cancelled")
DEFAULT_FILE = "scheduler.json"


class SchedulerError(Exception):
    pass


def valid_id(value):
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None and value.isascii()


def valid_priority(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 10


def find_cycle(jobs):
    """Return a list of ids forming a dependency cycle, or None."""
    color = {}
    for start in sorted(jobs):
        if start in color:
            continue
        color[start] = 1
        stack = [(start, iter(jobs[start]["depends_on"]))]
        path = [start]
        while stack:
            node, it = stack[-1]
            for dep in it:
                if dep not in jobs:
                    continue
                if color.get(dep) == 1:
                    return path[path.index(dep):] + [dep]
                if dep not in color:
                    color[dep] = 1
                    stack.append((dep, iter(jobs[dep]["depends_on"])))
                    path.append(dep)
                    break
            else:
                color[node] = 2
                stack.pop()
                path.pop()
    return None


def recompute_ready(jobs):
    """Every pending job whose dependencies are all done becomes ready."""
    for job in jobs.values():
        if job["status"] in ("pending", "ready"):
            all_done = all(jobs[d]["status"] == "done" for d in job["depends_on"])
            job["status"] = "ready" if all_done else "pending"


def execution_order(jobs):
    """Topological order; among available jobs, higher priority first (id breaks ties)."""
    remaining = {i: len(set(j["depends_on"])) for i, j in jobs.items()}
    dependents = {i: [] for i in jobs}
    for i, j in jobs.items():
        for d in set(j["depends_on"]):
            dependents[d].append(i)
    heap = [(-jobs[i]["priority"], i) for i, n in remaining.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, i = heapq.heappop(heap)
        order.append(i)
        for child in dependents[i]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(heap, (-jobs[child]["priority"], child))
    return order


def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise SchedulerError("cannot read %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise SchedulerError("%s: expected an object with a 'jobs' list" % path)
    jobs = {}
    for raw in data["jobs"]:
        if not isinstance(raw, dict):
            raise SchedulerError("%s: invalid job entry" % path)
        jid = raw.get("id")
        deps = raw.get("depends_on", [])
        if (not valid_id(jid) or jid in jobs or not isinstance(raw.get("name"), str)
                or not valid_priority(raw.get("priority"))
                or not isinstance(deps, list) or not all(valid_id(d) for d in deps)
                or raw.get("status") not in STATUSES):
            raise SchedulerError("%s: invalid job %r" % (path, jid))
        jobs[jid] = {"id": jid, "name": raw["name"], "priority": raw["priority"],
                     "depends_on": list(deps), "status": raw["status"]}
    for job in jobs.values():
        for d in job["depends_on"]:
            if d not in jobs:
                raise SchedulerError("%s: job %s has unknown dependency %s" % (path, job["id"], d))
    cycle = find_cycle(jobs)
    if cycle:
        raise SchedulerError("%s: dependency cycle: %s" % (path, " -> ".join(cycle)))
    recompute_ready(jobs)
    return jobs


def save(path, jobs):
    out = []
    for job in jobs.values():
        entry = dict(job)
        if entry["status"] == "ready":
            entry["status"] = "pending"  # ready is never persisted
        out.append(entry)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"jobs": out}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def add_job(jobs, jid, name, priority, depends_on):
    if not valid_id(jid):
        raise SchedulerError("invalid id %r: use 1-32 letters, digits or underscore" % (jid,))
    if not valid_priority(priority):
        raise SchedulerError("invalid priority %r: must be an integer 1-10" % (priority,))
    if not isinstance(name, str) or not name.strip():
        raise SchedulerError("name must not be empty")
    depends_on = list(dict.fromkeys(depends_on))
    for d in depends_on:
        if not valid_id(d):
            raise SchedulerError("invalid dependency id %r" % (d,))
    if jid in jobs:
        raise SchedulerError("duplicate id: %s" % jid)
    if jid in depends_on:
        raise SchedulerError("self-dependency: %s" % jid)
    for d in depends_on:
        if d not in jobs:
            raise SchedulerError("unknown dependency: %s" % d)
    job = {"id": jid, "name": name, "priority": priority,
           "depends_on": depends_on, "status": "pending"}
    trial = dict(jobs)
    trial[jid] = job
    cycle = find_cycle(trial)
    if cycle:
        raise SchedulerError("cycle detected: %s" % " -> ".join(cycle))
    if any(jobs[d]["status"] in ("failed", "cancelled") for d in depends_on):
        job["status"] = "cancelled"
    jobs[jid] = job
    recompute_ready(jobs)
    return job


def dependents_of(jobs, jid):
    found, stack = set(), [jid]
    while stack:
        cur = stack.pop()
        for j in jobs.values():
            if cur in j["depends_on"] and j["id"] not in found:
                found.add(j["id"])
                stack.append(j["id"])
    return found


def fail_job(jobs, jid):
    if jid not in jobs:
        raise SchedulerError("unknown job: %s" % jid)
    if jobs[jid]["status"] not in ("pending", "ready", "running"):
        raise SchedulerError("job %s is %s and cannot fail" % (jid, jobs[jid]["status"]))
    jobs[jid]["status"] = "failed"
    cancelled = sorted(dependents_of(jobs, jid))
    for d in cancelled:
        if jobs[d]["status"] not in ("done", "failed"):
            jobs[d]["status"] = "cancelled"
    recompute_ready(jobs)
    return cancelled


def pick_next(jobs):
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        return None
    return min(ready, key=lambda j: (-j["priority"], j["id"]))


def build_parser():
    p = argparse.ArgumentParser(prog="scheduler", description="Priority job scheduler")
    p.add_argument("--file", default=DEFAULT_FILE, help="state file (default: scheduler.json)")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add a job")
    a.add_argument("id")
    a.add_argument("name")
    a.add_argument("priority", type=int)
    a.add_argument("--depends-on", nargs="*", default=[], metavar="ID")
    sub.add_parser("run-next", help="run the highest-priority ready job")
    f = sub.add_parser("fail", help="mark a job failed and cancel its dependents")
    f.add_argument("id")
    sub.add_parser("status", help="list jobs and their status")
    sub.add_parser("report", help="summary and execution order")
    return p


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    try:
        jobs = load(args.file)
        if args.command == "add":
            job = add_job(jobs, args.id, args.name, args.priority, args.depends_on)
            save(args.file, jobs)
            print("added %s (%s)" % (job["id"], job["status"]))
        elif args.command == "run-next":
            job = pick_next(jobs)
            if job is None:
                print("no ready job")
            else:
                job["status"] = "running"
                save(args.file, jobs)
                print("running %s (%s)" % (job["id"], job["name"]))
                job["status"] = "done"
                recompute_ready(jobs)
                save(args.file, jobs)
                print("done %s" % job["id"])
        elif args.command == "fail":
            cancelled = fail_job(jobs, args.id)
            save(args.file, jobs)
            print("failed %s; cancelled: %s" % (args.id, ", ".join(cancelled) or "none"))
        elif args.command == "status":
            for jid in execution_order(jobs):
                j = jobs[jid]
                print("%s\t%s\tpriority=%d\tdepends_on=%s" % (
                    jid, j["status"], j["priority"], ",".join(j["depends_on"]) or "-"))
        elif args.command == "report":
            counts = {s: 0 for s in STATUSES}
            for j in jobs.values():
                counts[j["status"]] += 1
            print("jobs: %d" % len(jobs))
            for s in STATUSES:
                print("  %s: %d" % (s, counts[s]))
            order = [i for i in execution_order(jobs) if jobs[i]["status"] not in TERMINAL]
            print("execution order: %s" % (" -> ".join(order) or "(none)"))
    except SchedulerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
