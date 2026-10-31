Build a Priority Job Scheduler CLI in Python (single file scheduler.py, stdlib only). Requirements:
1. Jobs: id (alphanumeric and underscore, 1-32 chars, unique), name, priority (1-10), depends_on (list of ids).
2. Validation on add: reject duplicate id, self-dependency, unknown dependency.
3. Cycle detection: reject any add that would create a cycle.
4. Execution order: topological order with priority as tiebreak (higher first).
5. A job is ready when it is pending and all of its depends_on are done; recompute on load.
6. Failure propagation: when a job fails, all transitive dependents become cancelled.
7. Status values: pending, ready, running, done, failed, cancelled.
8. run-next: takes the highest-priority ready job, marks it running, then done (simulated).
9. Persistence in scheduler.json; ready is never persisted, it is recomputed on load.
10. Commands: add, run-next, fail <id>, status, report.
