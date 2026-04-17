import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

DEFAULT_FILE = "scheduler.json"
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,32}$")
VALID_STATUSES = {"pending", "ready", "running", "done", "failed", "cancelled"}


# a1 — persistence

def load_jobs(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open() as f:
        jobs = json.load(f)
    recompute_ready(jobs)
    return jobs


def save_jobs(jobs: dict, path: str) -> None:
    serialisable = {}
    for jid, job in jobs.items():
        entry = dict(job)
        # never persist ready — spec decision rule
        if entry.get("status") == "ready":
            entry["status"] = "pending"
        serialisable[jid] = entry
    with open(path, "w") as f:
        json.dump(serialisable, f, indent=2)


# a2 — recompute_ready

def recompute_ready(jobs: dict) -> None:
    for job in jobs.values():
        if job["status"] != "pending":
            continue
        if all(jobs[dep]["status"] == "done" for dep in job["depends_on"] if dep in jobs):
            job["status"] = "ready"


# a3 — cycle detection (DFS)

def has_cycle(jobs: dict, new_id: str, new_deps: list) -> bool:
    # build a temporary graph including the candidate job
    graph = {jid: list(job["depends_on"]) for jid, job in jobs.items()}
    graph[new_id] = new_deps

    visited = set()

    def dfs(node: str) -> bool:
        if node == new_id:
            return True
        if node in visited:
            return False
        visited.add(node)
        for neighbour in graph.get(node, []):
            if dfs(neighbour):
                return True
        return False

    for dep in new_deps:
        visited.clear()
        if dfs(dep):
            return True
    return False


# a4 — add command

def cmd_add(args, file: str) -> None:
    jobs = load_jobs(file)
    jid = args.id
    depends_on = args.depends_on or []

    if not ID_PATTERN.match(jid):
        print(f"Error: id '{jid}' is invalid (alphanumeric+underscore, 1-32 chars).", file=sys.stderr)
        sys.exit(1)
    if not (1 <= args.priority <= 10):
        print("Error: priority must be 1-10.", file=sys.stderr)
        sys.exit(1)
    if jid in jobs:
        print(f"Error: job '{jid}' already exists.", file=sys.stderr)
        sys.exit(1)
    if jid in depends_on:
        print(f"Error: job '{jid}' cannot depend on itself.", file=sys.stderr)
        sys.exit(1)
    for dep in depends_on:
        if dep not in jobs:
            print(f"Error: unknown dependency '{dep}'.", file=sys.stderr)
            sys.exit(1)
    if has_cycle(jobs, jid, depends_on):
        print(f"Error: adding '{jid}' would create a cycle.", file=sys.stderr)
        sys.exit(1)

    jobs[jid] = {
        "id": jid,
        "name": args.name,
        "priority": args.priority,
        "depends_on": depends_on,
        "status": "pending",
    }
    recompute_ready(jobs)
    save_jobs(jobs, file)
    print(f"Added: {jid}")


# a5 — run-next command

def cmd_run_next(args, file: str) -> None:
    jobs = load_jobs(file)
    ready = [j for j in jobs.values() if j["status"] == "ready"]
    if not ready:
        print("No jobs ready.")
        sys.exit(0)
    chosen = max(ready, key=lambda j: j["priority"])
    print(f"Running: {chosen['id']}")
    chosen["status"] = "running"
    chosen["status"] = "done"
    recompute_ready(jobs)
    save_jobs(jobs, file)


# a6 — propagate failure (BFS)

def propagate_failure(jobs: dict, failed_id: str) -> int:
    cancelled = set()
    queue = deque([failed_id])
    while queue:
        source = queue.popleft()
        for job in jobs.values():
            if source in job["depends_on"] and job["id"] not in cancelled and job["id"] != failed_id:
                cancelled.add(job["id"])
                queue.append(job["id"])
    for jid in cancelled:
        jobs[jid]["status"] = "cancelled"
    return len(cancelled)


# a7 — fail command

def cmd_fail(args, file: str) -> None:
    jobs = load_jobs(file)
    jid = args.job_id
    if jid not in jobs:
        print(f"Error: job '{jid}' not found.", file=sys.stderr)
        sys.exit(1)
    if jobs[jid]["status"] in ("done", "cancelled"):
        print(f"Error: job '{jid}' is already {jobs[jid]['status']}.", file=sys.stderr)
        sys.exit(1)
    jobs[jid]["status"] = "failed"
    n = propagate_failure(jobs, jid)
    recompute_ready(jobs)
    save_jobs(jobs, file)
    print(f"Failed: {jid}. Cancelled {n} downstream job(s).")


# a8 — status command

def cmd_status(args, file: str) -> None:
    jobs = load_jobs(file)
    if not jobs:
        print("No jobs.")
        return
    rows = sorted(jobs.values(), key=lambda j: -j["priority"])
    col_id = max(len("id"), max(len(j["id"]) for j in rows))
    col_name = max(len("name"), max(len(j["name"]) for j in rows))
    col_pri = len("priority")
    col_status = max(len("status"), max(len(j["status"]) for j in rows))
    header = (
        f"{'id':<{col_id}}  {'name':<{col_name}}  {'priority':<{col_pri}}  "
        f"{'status':<{col_status}}  depends_on"
    )
    print(header)
    print("-" * (len(header) + 20))
    for j in rows:
        deps = ", ".join(j["depends_on"]) if j["depends_on"] else "-"
        print(
            f"{j['id']:<{col_id}}  {j['name']:<{col_name}}  "
            f"{j['priority']:<{col_pri}}  {j['status']:<{col_status}}  {deps}"
        )


# a9 — report command

def cmd_report(args, file: str) -> None:
    jobs = load_jobs(file)
    counts: dict = {}
    for j in jobs.values():
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    if not counts:
        print("No jobs.")
        return
    for status in ["pending", "ready", "running", "done", "failed", "cancelled"]:
        if status in counts:
            print(f"  {status:<12} {counts[status]}")
    print(f"  {'total':<12} {sum(counts.values())}")


# a10 — argparse wiring

def build_parser(default_file: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scheduler")
    parser.add_argument("--file", default=default_file, help="State file (default: scheduler.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--priority", type=int, required=True)
    p_add.add_argument("--depends-on", nargs="*", dest="depends_on", default=[])

    sub.add_parser("run-next")

    p_fail = sub.add_parser("fail")
    p_fail.add_argument("job_id")

    sub.add_parser("status")
    sub.add_parser("report")

    return parser


def main() -> None:
    parser = build_parser(DEFAULT_FILE)
    args = parser.parse_args()
    dispatch = {
        "add": cmd_add,
        "run-next": cmd_run_next,
        "fail": cmd_fail,
        "status": cmd_status,
        "report": cmd_report,
    }
    dispatch[args.command](args, args.file)


if __name__ == "__main__":
    main()
