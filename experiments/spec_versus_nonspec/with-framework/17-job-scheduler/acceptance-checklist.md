# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A single-file Python CLI (scheduler.py) that manages jobs with dependency relationships, detects cycles, computes execution order via topological sort with priority tiebreak, propagates failures recursively, and persists state to a JSON file.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] After any add or run-next, ready status is recomputed correctly for all pending jobs.
- [ ] run-next picks the highest-priority ready job; prints its id before marking done.
- [ ] fail <id> sets target to failed and recursively sets all transitive dependents to cancelled.
- [ ] status prints a table with columns id, name, priority, status, depends_on.
- [ ] report prints counts per status (only statuses with count > 0).
- [ ] Cycle in the dependency graph is detected and rejected with a clear error message.

## Required Evidence
- [ ] add build --priority 8 succeeds; add test --depends-on build --priority 7 succeeds.
- [ ] add cycle --depends-on cycle is rejected (self-dep).
- [ ] Adding an edge that closes a cycle (A→B→A) is rejected.
- [ ] run-next after adding build and lint (priority 6, no deps) runs build first (higher priority).
- [ ] After build is done, test becomes ready; run-next runs test.
- [ ] fail deploy sets deploy=failed; notify (depends on deploy) becomes cancelled.
- [ ] status table displays all fields correctly.
- [ ] report shows correct counts after a mixed-state scenario.

## Decision Rules Compliance
- [ ] Cycle check must run BEFORE writing to scheduler.json — never persist a cyclic graph.
- [ ] recompute_ready must run after every state change (add, run-next, fail) before save.
- [ ] ready is never written to scheduler.json — always recomputed on load.
- [ ] propagate_failure must use BFS/DFS to find ALL transitive dependents, not just direct children.
- [ ] If a job is already failed/cancelled/done, fail command should print an error and exit 1.
- [ ] Priority tiebreak in run-next: higher number wins. If equal, any order is acceptable.
