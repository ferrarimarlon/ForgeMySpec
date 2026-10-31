import json, os, subprocess, sys, tempfile, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STDLIB = set(sys.stdlib_module_names)

class Side:
    def __init__(self, name):
        self.name = name; self.script = os.path.join(ROOT, name, "scheduler.py")
    def new(self):
        self.d = tempfile.mkdtemp(); self.f = os.path.join(self.d, "scheduler.json")
    def run(self, *args):
        return subprocess.run([sys.executable, self.script, *args], cwd=self.d,
                              capture_output=True, text=True, timeout=10)
    def add(self, jid, prio, deps=(), name="job"):
        a = ["add", "--id", jid, "--name", name, "--priority", str(prio)]
        if deps:
            a += ["--depends-on"] + (list(deps) if self.name == "A" else [",".join(deps)])
        return self.run(*a)
    def state(self):
        with open(self.f) as fh: return {j["id"]: j for j in json.load(fh)["jobs"]}
    def raw(self):
        return open(self.f).read() if os.path.exists(self.f) else None
    def write(self, jobs):
        with open(self.f, "w") as fh: json.dump({"jobs": jobs}, fh)

def J(i, p=5, deps=(), st="pending"):
    return {"id": i, "name": i, "priority": p, "depends_on": list(deps), "status": st}

def P01(s):  # stdlib only, single file
    t = ast.parse(open(s.script).read()); mods = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    return mods <= STDLIB
def P02(s):
    s.new(); r = s.add("ok_1", 5)
    return r.returncode == 0 and os.path.exists(s.f) and "ok_1" in s.state()
def P03(s):
    s.new(); bad = ["a-b", "a b", "x"*33, "", "é1"]
    ok = all(s.add(b, 5).returncode != 0 for b in bad)
    return ok and s.add("A_"+"9"*30, 5).returncode == 0 and not (os.path.exists(s.f) and set(s.state()) - {"A_"+"9"*30})
def P04(s):
    s.new(); s.add("a", 5); before = s.raw(); r = s.add("a", 6)
    return r.returncode != 0 and s.raw() == before
def P05(s):
    s.new()
    return all(s.add("p%s" % i, p).returncode != 0 for i, p in enumerate(["0", "11", "-1", "abc", "5.5"])) \
        and s.add("lo", 1).returncode == 0 and s.add("hi", 10).returncode == 0
def P06(s):
    s.new(); s.add("a", 5); before = s.raw(); r = s.add("b", 5, ["b"])
    return r.returncode != 0 and s.raw() == before
def P07(s):
    s.new(); s.add("a", 5); before = s.raw(); r = s.add("b", 5, ["zzz"])
    return r.returncode != 0 and s.raw() == before
def P08(s):  # cyclic state must be detected, not loop
    s.new(); s.write([J("a", deps=["b"]), J("b", deps=["a"])])
    try: r = s.add("c", 5, ["a"])
    except subprocess.TimeoutExpired: return False
    return r.returncode != 0
def P09(s):  # report topo + priority
    s.new(); s.add("a", 1); s.add("b", 10); s.add("c", 5, ["a"]); s.add("d", 9, ["b"])
    out = s.run("report").stdout
    pos = {k: out.find(" %s " % k) for k in "abcd"}
    if min(pos.values()) < 0: return False
    order = sorted(pos, key=pos.get)
    return order == ["b", "d", "a", "c"]
def P10(s):  # run-next priority
    s.new(); s.add("a", 1); s.add("b", 10); s.add("c", 5)
    s.run("run-next"); st = s.state()
    return st["b"]["status"] == "done" and st["a"]["status"] == "pending" and st["c"]["status"] == "pending"
def P11(s):  # run-next respects deps
    s.new(); s.add("a", 1); s.add("b", 10, ["a"])
    s.run("run-next"); st = s.state()
    ok1 = st["a"]["status"] == "done" and st["b"]["status"] == "pending"
    s.run("run-next"); st = s.state()
    return ok1 and st["b"]["status"] == "done"
def P12(s):  # ready never persisted
    s.new(); s.add("a", 1); s.add("b", 2, ["a"]); s.run("run-next")
    return '"ready"' not in s.raw()
def P13(s):  # ready recomputed on load, including persisted bogus ready
    s.new(); s.write([J("a", st="done"), J("b", deps=["a"]), J("c", deps=["b"], st="ready")])
    out = s.run("status").stdout
    lines = {l.split()[0]: l for l in out.splitlines() if l.strip()}
    return "ready" in lines.get("b", "") and "ready" not in lines.get("c", "") and "pending" in lines.get("c", "")
def P14(s):  # transitive cancel
    s.new(); s.add("a", 5); s.add("b", 5, ["a"]); s.add("c", 5, ["b"]); s.add("x", 5)
    r = s.run("fail", "a"); st = s.state()
    return r.returncode == 0 and st["a"]["status"] == "failed" and st["b"]["status"] == "cancelled" \
        and st["c"]["status"] == "cancelled" and st["x"]["status"] == "pending"
def P15(s):  # diamond cancel
    s.new(); s.add("a", 5); s.add("b", 5, ["a"]); s.add("c", 5, ["a"]); s.add("d", 5, ["b", "c"])
    s.run("fail", "b"); st = s.state()
    return st["d"]["status"] == "cancelled" and st["c"]["status"] == "pending" and st["a"]["status"] == "pending"
def P16(s):  # statuses within allowed set
    s.new(); s.add("a", 5); s.add("b", 5, ["a"]); s.add("c", 4); s.run("run-next"); s.run("fail", "c")
    allowed = {"pending", "running", "done", "failed", "cancelled"}
    return all(j["status"] in allowed for j in s.state().values())
def P17(s):  # run-next nothing ready
    s.new(); s.add("a", 5); s.run("fail", "a"); before = s.raw(); r = s.run("run-next")
    return "Traceback" not in r.stderr and s.raw() == before
def P18(s):
    s.new(); s.add("a", 5); r = s.run("fail", "nope")
    return r.returncode != 0 and "Traceback" not in r.stderr
def P19(s):  # all commands work
    s.new(); s.add("a", 5)
    return all(s.run(*c).returncode == 0 for c in (["status"], ["report"], ["run-next"]))
def P20(s):  # corrupt file -> clean error
    s.new(); open(s.f, "w").write("{not json")
    r = s.run("status"); return r.returncode != 0 and "Traceback" not in r.stderr
def P21(s):  # persistence file named scheduler.json in cwd
    s.new(); s.add("a", 5); return os.listdir(s.d) == ["scheduler.json"]

probes = {k: v for k, v in sorted(globals().items()) if k.startswith("P") and k[1:].isdigit()}
res = {}
for side in ("A", "B"):
    s = Side(side); res[side] = {}
    for k, fn in probes.items():
        try: res[side][k] = "pass" if fn(s) else "fail"
        except Exception as e: res[side][k] = "fail"; print(side, k, repr(e))
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for side in res: print(side, sum(v == "pass" for v in res[side].values()), [k for k, v in res[side].items() if v != "pass"])
