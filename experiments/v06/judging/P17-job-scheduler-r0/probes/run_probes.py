import json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def mk(side):
    d = tempfile.mkdtemp()
    script = os.path.join(ROOT, side, "scheduler.py")
    def run(*a):
        return subprocess.run([sys.executable, "-I", script, *a], cwd=d, capture_output=True, text=True)
    def add(i, p=5, deps=None, name=None):
        a = ["add", "--id", i, "--name", name or ("job " + i), "--priority", str(p)]
        if deps: a += ["--depends-on", ",".join(deps)]
        return run(*a)
    def state():
        f = os.path.join(d, "scheduler.json")
        return json.load(open(f)) if os.path.exists(f) else None
    def st(i):
        out = run("status").stdout
        for line in out.splitlines():
            toks = line.split()
            if toks and toks[0] == i:
                for s in ("pending","ready","running","done","failed","cancelled"):
                    if s in toks: return s
        return None
    return d, run, add, state, st

def jobs_of(s):
    return s["jobs"] if isinstance(s, dict) else s

P = {}
def probe(f): P[f.__name__] = f; return f

@probe
def p01_add_valid(e):
    d, run, add, state, st = e
    r = add("job_1", 5)
    return r.returncode == 0 and st("job_1") == "ready" and len(jobs_of(state())) == 1
@probe
def p02_invalid_id_chars(e):
    d, run, add, state, st = e
    return add("bad-id").returncode != 0 and add("a b").returncode != 0 and add("").returncode != 0
@probe
def p03_id_length(e):
    d, run, add, state, st = e
    return add("a"*32).returncode == 0 and add("b"*33).returncode != 0
@probe
def p04_id_trailing_newline(e):
    d, run, add, state, st = e
    add("x", 5)
    return add("abc\n").returncode != 0
@probe
def p05_priority_range(e):
    d, run, add, state, st = e
    return (add("a",0).returncode != 0 and add("b",11).returncode != 0
            and add("c",1).returncode == 0 and add("d",10).returncode == 0)
@probe
def p06_duplicate(e):
    d, run, add, state, st = e
    add("a"); r = add("a")
    return r.returncode != 0 and len(jobs_of(state())) == 1
@probe
def p07_self_dep(e):
    d, run, add, state, st = e
    r = add("a", deps=["a"])
    s = state()
    return r.returncode != 0 and (s is None or len(jobs_of(s)) == 0)
@probe
def p08_unknown_dep(e):
    d, run, add, state, st = e
    r = add("a", deps=["nope"]); s = state()
    return r.returncode != 0 and (s is None or len(jobs_of(s)) == 0)
@probe
def p09_cycle_rejected(e):
    # pre-seeded state where x depends on y (not yet present); adding y->x would close a cycle
    d, run, add, state, st = e
    json.dump({"jobs":[{"id":"x","name":"x","priority":5,"depends_on":["y"],"status":"pending"}]},
              open(os.path.join(d,"scheduler.json"),"w"))
    r = add("y", deps=["x"])
    s = state()
    return r.returncode != 0 and not any(j["id"]=="y" for j in jobs_of(s))
@probe
def p10_ready_requires_deps_done(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"])
    ok1 = st("a") == "ready" and st("b") == "pending"
    run("run-next")
    return ok1 and st("a") == "done" and st("b") == "ready"
@probe
def p11_ready_not_persisted(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"]); run("run-next")
    return all(j["status"] != "ready" for j in jobs_of(state()))
@probe
def p12_ready_recomputed_on_load(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"])
    s = state()
    for j in jobs_of(s):
        if j["id"] == "a": j["status"] = "done"
    json.dump(s, open(os.path.join(d,"scheduler.json"),"w"))
    return st("b") == "ready"
@probe
def p13_run_next_priority(e):
    d, run, add, state, st = e
    add("low", 2); add("high", 9); add("mid", 5)
    r = run("run-next")
    return r.returncode == 0 and st("high") == "done" and st("low") in ("ready",) and st("mid") == "ready"
@probe
def p14_run_next_sequence(e):
    d, run, add, state, st = e
    add("a", 1); add("b", 10, deps=["a"]); add("c", 5)
    run("run-next")  # c (only a,c ready; c higher)
    first = st("c") == "done" and st("a") == "ready"
    run("run-next")  # a
    run("run-next")  # b
    return first and all(st(x) == "done" for x in "abc")
@probe
def p15_run_next_empty(e):
    d, run, add, state, st = e
    r = run("run-next")
    return "Traceback" not in r.stderr
@probe
def p16_fail_transitive(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"]); add("c", deps=["b"]); add("d", deps=["c"]); add("e")
    r = run("fail", "a")
    return (r.returncode == 0 and st("a") == "failed" and st("b") == "cancelled"
            and st("c") == "cancelled" and st("d") == "cancelled" and st("e") == "ready")
@probe
def p17_fail_diamond(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"]); add("c", deps=["a"]); add("d", deps=["b","c"])
    run("fail", "b")
    return st("b") == "failed" and st("d") == "cancelled" and st("c") == "pending" and st("a") == "ready"
@probe
def p18_fail_unknown(e):
    d, run, add, state, st = e
    r = run("fail", "zzz")
    return r.returncode != 0 and "Traceback" not in r.stderr
@probe
def p19_fail_persisted(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"]); run("fail", "a")
    m = {j["id"]: j["status"] for j in jobs_of(state())}
    return m == {"a": "failed", "b": "cancelled"}
@probe
def p20_status_values_valid(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"]); add("c"); run("run-next"); run("fail", "c")
    ok = {"pending","running","done","failed","cancelled"}
    return all(j["status"] in ok for j in jobs_of(state()))
@probe
def p21_report_topo_priority(e):
    d, run, add, state, st = e
    add("a", 1); add("b", 10, deps=["a"]); add("c", 5)
    r = run("report"); out = r.stdout
    try:
        ia, ib, ic = out.index(" a "), out.index(" b "), out.index(" c ")
    except ValueError:
        import re
        pos = {k: re.search(r"\b%s\b" % k, out.split("rder")[1]).start() for k in "abc"}
        ia, ib, ic = pos["a"], pos["b"], pos["c"]
    return r.returncode == 0 and ic < ia < ib
@probe
def p22_report_runs(e):
    d, run, add, state, st = e
    add("a"); run("fail","a"); r = run("report")
    return r.returncode == 0 and "failed" in r.stdout.lower()
@probe
def p23_status_runs_empty(e):
    d, run, add, state, st = e
    r = run("status")
    return r.returncode == 0 and "Traceback" not in r.stderr
@probe
def p24_add_after_failed_dep_cancelled(e):
    d, run, add, state, st = e
    add("a"); run("fail","a"); add("b", deps=["a"])
    return st("b") == "cancelled"
@probe
def p25_corrupt_state_no_traceback(e):
    d, run, add, state, st = e
    open(os.path.join(d,"scheduler.json"),"w").write("{not json")
    r = run("status")
    return r.returncode != 0 and "Traceback" not in r.stderr
@probe
def p26_fail_done_job_rejected(e):
    d, run, add, state, st = e
    add("a"); add("b", deps=["a"]); run("run-next")
    r = run("fail","a")
    return r.returncode != 0 and st("a") == "done" and st("b") == "ready"

res = {}
for side in ("A","B"):
    res[side] = {}
    for k, f in P.items():
        try: res[side][k] = "pass" if f(mk(side)) else "fail"
        except Exception as ex: res[side][k] = "fail"
json.dump(res, open(os.path.join(ROOT,"probes","results.json"),"w"), indent=1)
for k in P: print(k, res["A"][k], res["B"][k])
