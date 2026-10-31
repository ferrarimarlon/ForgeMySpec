import json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def mk(side):
    d = tempfile.mkdtemp()
    script = os.path.join(ROOT, side, "scheduler.py")
    def run(*args):
        args = list(args)
        if side == "B" and args[0] == "add":
            # adapter: add ID NAME PRIO [deps...] -> flags
            jid, name, pr, *deps = args[1:]
            args = ["add", "--id", jid, "--name", name, "--priority", pr]
            if deps: args += ["--depends-on"] + deps
        elif side == "A" and args[0] == "add":
            jid, name, pr, *deps = args[1:]
            args = ["add", jid, name, pr] + (["--depends-on"] + deps if deps else [])
        p = subprocess.run([sys.executable, script] + args, cwd=d, capture_output=True, text=True,
                           env={**os.environ, "HOME": d})
        return p.returncode, p.stdout + p.stderr
    def state():
        with open(os.path.join(d, "scheduler.json")) as f: return json.load(f)
    def status_of(jid):
        return {j["id"]: j["status"] for j in state()["jobs"]}.get(jid)
    return d, run, state, status_of

def jobs_by_id(st): return {j["id"]: j for j in st["jobs"]}

P = {}
def probe(f): P[f.__name__] = f; return f

@probe
def p01_add_basic_persists(side):
    d, run, st, s = mk(side)
    rc, _ = run("add", "a", "Job A", "5")
    j = jobs_by_id(st()).get("a")
    return rc == 0 and j and j["name"] == "Job A" and j["priority"] == 5 and j["depends_on"] == []
@probe
def p02_invalid_id_chars(side):
    d, run, st, s = mk(side)
    rc, _ = run("add", "a-b", "x", "5")
    return rc != 0 and not os.path.exists(os.path.join(d, "scheduler.json")) or (rc != 0 and "a-b" not in jobs_by_id(st()))
@probe
def p03_id_length(side):
    d, run, st, s = mk(side)
    rc1, _ = run("add", "x"*32, "x", "5")
    rc2, _ = run("add", "y"*33, "x", "5")
    rc3, _ = run("add", "", "x", "5")
    return rc1 == 0 and rc2 != 0 and rc3 != 0
@probe
def p04_unicode_id_rejected(side):
    d, run, st, s = mk(side)
    rc, _ = run("add", "é1", "x", "5")
    return rc != 0
@probe
def p05_priority_range(side):
    d, run, st, s = mk(side)
    r = [run("add", "p%d" % i, "x", str(v))[0] for i, v in enumerate([0, 1, 10, 11, -1])]
    return r[0] != 0 and r[1] == 0 and r[2] == 0 and r[3] != 0 and r[4] != 0
@probe
def p06_priority_non_int(side):
    d, run, st, s = mk(side)
    return run("add", "a", "x", "abc")[0] != 0
@probe
def p07_duplicate_rejected(side):
    d, run, st, s = mk(side)
    run("add", "a", "first", "5")
    rc, _ = run("add", "a", "second", "6")
    return rc != 0 and jobs_by_id(st())["a"]["name"] == "first" and len(st()["jobs"]) == 1
@probe
def p08_self_dep_rejected(side):
    d, run, st, s = mk(side)
    run("add", "z", "z", "5")
    rc, _ = run("add", "a", "x", "5", "a")
    return rc != 0 and "a" not in jobs_by_id(st())
@probe
def p09_unknown_dep_rejected(side):
    d, run, st, s = mk(side)
    run("add", "z", "z", "5")
    rc, _ = run("add", "a", "x", "5", "nope")
    return rc != 0 and "a" not in jobs_by_id(st())
@probe
def p10_cycle_via_tampered_file_not_accepted(side):
    # cycle cannot be created by add alone; check add of a job into a file with a cycle doesn't silently succeed
    d, run, st, s = mk(side)
    with open(os.path.join(d, "scheduler.json"), "w") as f:
        json.dump({"jobs": [
            {"id": "a", "name": "a", "priority": 1, "depends_on": ["b"], "status": "pending"},
            {"id": "b", "name": "b", "priority": 1, "depends_on": ["a"], "status": "pending"}]}, f)
    rc, _ = run("add", "c", "c", "5", "a")
    return rc != 0
@probe
def p11_topo_order_priority_tiebreak(side):
    d, run, st, s = mk(side)
    run("add", "low", "l", "1"); run("add", "high", "h", "9")
    run("add", "child", "c", "10", "low")
    order = []
    for _ in range(3):
        rc, out = run("run-next")
        for tok in ["low", "high", "child"]:
            if ("running " + tok) in out: order.append(tok)
    return order == ["high", "low", "child"]
@probe
def p12_dep_before_dependent(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "10", "a")
    rc, out = run("run-next")
    return "a" in out and s("a") == "done" and s("b") == "pending"
@probe
def p13_ready_not_persisted(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "5", "a"); run("run-next")
    sts = [j["status"] for j in st()["jobs"]]
    return "ready" not in sts and s("b") == "pending"
@probe
def p14_ready_recomputed_on_load(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "5", "a")
    data = st()
    for j in data["jobs"]:
        if j["id"] == "a": j["status"] = "done"
    with open(os.path.join(d, "scheduler.json"), "w") as f: json.dump(data, f)
    rc, out = run("run-next")
    return rc == 0 and "b" in out and s("b") == "done"
@probe
def p15_status_shows_ready(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "5", "a")
    rc, out = run("status")
    lines = out.splitlines()
    la = [l for l in lines if l.split() and l.split()[0] == "a"]
    lb = [l for l in lines if l.split() and l.split()[0] == "b"]
    return rc == 0 and la and "ready" in la[0] and lb and "pending" in lb[0]
@probe
def p16_fail_transitive_cancel(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "1", "a"); run("add", "c", "c", "1", "b")
    run("add", "e", "e", "1")
    rc, _ = run("fail", "a")
    return rc == 0 and s("a") == "failed" and s("b") == "cancelled" and s("c") == "cancelled" and s("e") == "pending"
@probe
def p17_fail_diamond(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "x", "x", "1")
    run("add", "b", "b", "1", "a", "x"); run("add", "c", "c", "1", "b")
    run("run-next")  # some job done
    run("fail", "a") if s("a") != "done" else run("fail", "x")
    return s("b") == "cancelled" and s("c") == "cancelled"
@probe
def p18_fail_unknown(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1")
    return run("fail", "nope")[0] != 0
@probe
def p19_cancelled_not_run(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "9", "a"); run("fail", "a")
    rc, out = run("run-next")
    return s("b") == "cancelled" and "running" not in out
@probe
def p20_runnext_empty_graceful(side):
    d, run, st, s = mk(side)
    rc, out = run("run-next")
    return "Traceback" not in out
@probe
def p21_status_values_valid(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "1", "a"); run("add", "c", "c", "1")
    run("run-next"); run("fail", "c")
    ok = {"pending", "ready", "running", "done", "failed", "cancelled"}
    return all(j["status"] in ok for j in st()["jobs"])
@probe
def p22_report_runs(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("add", "b", "b", "1", "a"); run("fail", "a")
    rc, out = run("report")
    return rc == 0 and "failed" in out.lower() and "cancelled" in out.lower() and "Traceback" not in out
@probe
def p23_corrupt_file_clean_error(side):
    d, run, st, s = mk(side)
    with open(os.path.join(d, "scheduler.json"), "w") as f: f.write("{not json")
    rc, out = run("status")
    return rc != 0 and "Traceback" not in out
@probe
def p24_dangling_dep_file_clean_error(side):
    d, run, st, s = mk(side)
    with open(os.path.join(d, "scheduler.json"), "w") as f:
        json.dump({"jobs": [{"id": "a", "name": "a", "priority": 1, "depends_on": ["ghost"], "status": "pending"}]}, f)
    rc, out = run("status")
    return rc != 0 and "Traceback" not in out
@probe
def p25_add_after_failed_dep(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1"); run("fail", "a")
    run("add", "b", "b", "1", "a")
    return s("b") in ("cancelled",) 
@probe
def p26_writes_scheduler_json_in_cwd(side):
    d, run, st, s = mk(side)
    run("add", "a", "a", "1")
    return os.path.exists(os.path.join(d, "scheduler.json"))

if __name__ == "__main__":
    res = {}
    for side in ("A", "B"):
        res[side] = {}
        for name, f in P.items():
            try: ok = bool(f(side))
            except Exception as e: ok = False; print(side, name, "EXC", e)
            res[side][name] = "pass" if ok else "fail"
    json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
    for name in P: print(name, res["A"][name], res["B"][name])
