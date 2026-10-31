import json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def add_args(side, jid, name, pr, deps=None):
    if side == "A":
        a = ["add", "--id", jid, "--name", name, "--priority", str(pr)]
        if deps: a += ["--depends-on", ",".join(deps)]
    else:
        a = ["add", jid, name, "-p", str(pr)]
        if deps: a += ["-d", ",".join(deps)]
    return a

class S:
    def __init__(self, side):
        self.side = side; self.d = tempfile.mkdtemp()
        self.script = os.path.join(ROOT, side, "scheduler.py")
    def run(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "SCHEDULER_FILE"}
        return subprocess.run([sys.executable, "-I", self.script, *args], cwd=self.d,
                              capture_output=True, text=True, env=env, timeout=20)
    def add(self, *a, **k): return self.run(*add_args(self.side, *a, **k))
    @property
    def path(self): return os.path.join(self.d, "scheduler.json")
    def state(self):
        with open(self.path) as f: return {j["id"]: j for j in json.load(f)["jobs"]}
    def raw(self):
        return open(self.path).read() if os.path.exists(self.path) else None
    def status_of(self, jid):
        out = self.run("status").stdout
        for line in out.splitlines():
            t = line.split()
            if t and t[0] == jid:
                for s in ("pending","ready","running","done","failed","cancelled"):
                    if s in t: return s
        return None

def ok(r): return r.returncode == 0 and "Traceback" not in r.stderr
def rej(r): return r.returncode != 0 and "Traceback" not in r.stderr

def p01(s):
    r = s.add("job_1", "First", 5); st = s.state()
    return ok(r) and st["job_1"]["name"] == "First" and st["job_1"]["priority"] == 5 and st["job_1"]["depends_on"] == []
def p02(s):
    return all(rej(s.add(i, "x", 5)) for i in ["a-b", "a b", "", "é"]) and s.raw() is None
def p03(s):
    return rej(s.add("a"*33, "x", 5)) and ok(s.add("a"*32, "x", 5))
def p04(s):
    return rej(s.add("a", "x", 0)) and rej(s.add("b", "x", 11)) and ok(s.add("c", "x", 1)) and ok(s.add("d", "x", 10))
def p05(s):
    s.add("a", "x", 5); before = s.raw()
    return rej(s.add("a", "y", 6)) and s.raw() == before
def p06(s):
    return rej(s.add("a", "x", 5, ["a"])) and s.raw() is None
def p07(s):
    return rej(s.add("a", "x", 5, ["nope"])) and s.raw() is None
def p08(s):
    # pre-existing state: x depends on y (y not yet present); adding y->x would close a cycle
    with open(s.path, "w") as f:
        json.dump({"jobs": [{"id": "x", "name": "x", "priority": 5, "depends_on": ["y"], "status": "pending"}]}, f)
    before = s.raw(); r = s.add("y", "y", 5, ["x"])
    return rej(r) and s.raw() == before
def order_from(out, ids):
    pos = {i: (m.start() if (m := re.search(r"(?<![\w])" + i + r"(?![\w])", out)) else -1) for i in ids}
    return sorted(ids, key=lambda i: pos[i]) if all(v >= 0 for v in pos.values()) else None
def p09(s):
    s.add("low", "l", 1); s.add("high", "h", 9); s.add("child", "c", 10, ["low"]); s.add("mid", "m", 5, ["high"])
    o = order_from(s.run("report").stdout, ["low", "high", "child", "mid"])
    return o == ["high", "mid", "low", "child"] or o == ["high", "low", "child", "mid"] and False
def p10(s):
    s.add("low", "l", 1); s.add("high", "h", 9); s.add("child", "c", 10, ["low"])
    seq = []
    for _ in range(3):
        before = s.state(); r = s.run("run-next"); after = s.state()
        done = [i for i in after if after[i]["status"] == "done" and before[i]["status"] != "done"]
        if not ok(r) or len(done) != 1: return False
        seq.append(done[0])
    return seq == ["high", "low", "child"]
def p11(s):
    s.add("a", "a", 5); s.add("b", "b", 5, ["a"])
    return '"ready"' not in s.raw() and s.status_of("a") == "ready" and s.status_of("b") == "pending"
def p12(s):
    s.add("a", "a", 5); s.add("b", "b", 5, ["a"]); s.add("c", "c", 5, ["b"]); s.add("e", "e", 5, ["a", "d0"]) if False else None
    s.add("d", "d", 5); s.add("e", "e", 5, ["d", "c"])
    r = s.run("fail", "a"); st = s.state()
    return ok(r) and st["a"]["status"] == "failed" and all(st[i]["status"] == "cancelled" for i in "bce") and st["d"]["status"] == "pending"
def p13(s):
    s.add("a", "a", 5); s.add("b", "b", 5, ["a"]); s.add("c", "c", 5); s.run("run-next"); s.run("fail", "c") ; s.add("d","d",3)
    st = s.state(); allowed = {"pending","running","done","failed","cancelled"}
    shown = {s.status_of(i) for i in st}
    return all(j["status"] in allowed for j in st.values()) and shown <= allowed | {"ready"}
def p14(s):
    r1 = s.run("run-next"); s.add("a", "a", 5); s.run("run-next"); r2 = s.run("run-next")
    return ok(r1) and ok(r2) and s.state()["a"]["status"] == "done"
def p15(s):
    s.add("a", "a", 5); before = s.raw()
    return rej(s.run("fail", "zz")) and s.raw() == before
def p16(s):
    with open(s.path, "w") as f: f.write("{not json")
    rs = [s.run("status"), s.run("report"), s.run("run-next")]
    return all(rej(r) for r in rs)
def p17(s):
    with open(s.path, "w") as f:
        json.dump({"jobs": [{"id": "a", "name": "a", "priority": 5, "depends_on": [], "status": "done"},
                            {"id": "b", "name": "b", "priority": 5, "depends_on": ["a"], "status": "pending"}]}, f)
    return s.status_of("b") == "ready"
def p18(s):
    s.add("a", "a", 5); s.add("b", "b", 5, ["a"]); s.run("run-next"); s.run("run-next")
    return '"ready"' not in s.raw() and s.state()["b"]["status"] == "done"
def p19(s):
    s.add("a", "a", 5)
    return all(ok(s.run(c)) for c in ["status", "report"]) and ok(s.run("fail", "a"))
def p20(s):
    # job added after its dependency failed must never become ready / be run
    s.add("a", "a", 5); s.run("fail", "a"); s.add("b", "b", 5, ["a"]); s.run("run-next")
    return s.state()["b"]["status"] not in ("done", "running") and s.status_of("b") != "ready"
def p21(s):
    # fail of done job rejected or no-op (must not mark done dependents cancelled)
    s.add("a", "a", 5); s.add("b", "b", 5, ["a"]); s.run("run-next"); s.run("run-next")
    s.run("fail", "a"); st = s.state()
    return st["b"]["status"] == "done"

def p22(s):
    with open(s.path, "w") as f:
        json.dump({"jobs": [{"id": "a", "name": "a", "priority": "x", "depends_on": [], "status": "pending"}]}, f)
    return all(rej(s.run(c)) for c in ["status", "report", "run-next"])
def p23(s):
    with open(s.path, "w") as f:
        json.dump({"jobs": [{"id": "a", "name": "a", "priority": 5, "depends_on": ["b"], "status": "pending"},
                            {"id": "b", "name": "b", "priority": 5, "depends_on": ["a"], "status": "pending"}]}, f)
    r = s.run("report")
    return rej(r) or ("Traceback" not in r.stderr and "cycle" in (r.stdout + r.stderr).lower())

PROBES = {k: v for k, v in globals().items() if re.fullmatch(r"p\d\d", k)}
res = {}
for side in ("A", "B"):
    res[side] = {}
    for k, fn in sorted(PROBES.items()):
        try: res[side][k] = "pass" if fn(S(side)) else "fail"
        except Exception as e: res[side][k] = "fail"; print(side, k, "EXC", repr(e))
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(res))
