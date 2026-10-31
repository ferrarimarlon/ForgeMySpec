"""Black-box probes. Usage: python3 run_probes.py <dir-with-state_machine.py> <side>"""
import json, os, re, subprocess, sys, tempfile
SIDE_DIR = os.path.abspath(sys.argv[1])
PROG = os.path.join(SIDE_DIR, "state_machine.py")

def mk(defn, finals=None):
    d = dict(defn)
    f = finals if finals is not None else d.pop("_finals", [])
    # interface adaptation only: definition carries both spellings of the finals key
    d["final"] = f; d["finals"] = f
    return d

BASE = {"states": ["idle", "running", "done"], "initial": "idle", "_finals": ["done"],
        "transitions": [{"from": "idle", "event": "start", "to": "running"},
                        {"from": "running", "event": "finish", "to": "done",
                         "guard": {"key": "progress", "op": ">=", "value": 100}}]}

def run(defn, *args, raw=None, cwd=None):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.json")
        with open(p, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(defn))
        r = subprocess.run([sys.executable, "-I", PROG, p, *args], capture_output=True,
                           text=True, cwd=cwd or td, timeout=20)
        return r.returncode, r.stdout, r.stderr

def notb(err): return "Traceback" not in err
def var(**kw):
    d = json.loads(json.dumps(BASE)); d.update(kw); return mk(d)

res = {}
def probe(pid, fn):
    try: res[pid] = "pass" if fn() else "fail"
    except Exception as e: res[pid] = "fail"; print(pid, "EXC", e, file=sys.stderr)

def p01():
    c, o, e = run(var(), "start", "finish", "--context", '{"progress": 100}')
    return c == 0 and re.search(r"state: done", o) and notb(e)
def p02():
    d = var(); d["transitions"].append({"from": "idle", "event": "x", "to": "nowhere"})
    c, o, e = run(d); return c != 0 and "nowhere" in (o + e) and notb(e)
def p03():
    c, o, e = run(var(initial="ghost")); return c != 0 and "ghost" in (o+e) and notb(e)
def p04():
    d = var(); d["states"].append("island")
    c, o, e = run(d); return c != 0 and "island" in (o+e) and "unreachable" in (o+e).lower() and notb(e)
def p05():
    d = var(); del d["initial"]
    c, o, e = run(d); return c != 0 and "initial" in (o+e).lower() and notb(e)
def p06():
    c, o, e = run(var(), "start", "finish", "--context", '{"progress": 100}')
    return "done" in o and c == 0
def p07():
    c, o, e = run(var(), "start", "finish", "--context", '{"progress": 50}')
    return re.search(r"state: running\b", o) is not None and notb(e)
def p08():
    c, o, e = run(var(), "bogus"); return re.search(r"state: idle\b", o) is not None and notb(e)
def p09():
    c, o, e = run(None, raw="{not json"); return c != 0 and notb(e)
def p10():
    r = subprocess.run([sys.executable, "-I", PROG, "/nonexistent/x.json"], capture_output=True, text=True)
    return r.returncode != 0 and notb(r.stderr)
def p11():
    d = var(); d["final"] = d["finals"] = ["ghostfinal"]
    c, o, e = run(d); return c != 0 and "ghostfinal" in (o+e) and notb(e)
def p12():
    c, o, e = run(var(initial=["idle"])); return c != 0 and notb(e)
def p13():
    with tempfile.TemporaryDirectory() as td:
        marker = os.path.join(td, "PWNED")
        d = var(); d["transitions"][0]["guard"] = f"__import__('os').system('touch {marker}')"
        c, o, e = run(d, "start", cwd=td)
        return not os.path.exists(marker) and notb(e)
def p14():
    c, o, e = run(var(), "start", "finish", "--context", '{"progress": 100}')
    i1 = o.find("idle"); i2 = o.find("running"); i3 = o.rfind("done")
    lines = [l for l in o.splitlines() if "idle" in l and "running" in l]
    lines2 = [l for l in o.splitlines() if "running" in l and "done" in l and "start" not in l]
    return bool(lines) and bool(lines2) and o.find(lines[0]) < o.find(lines2[0])
def p15():
    src = open(PROG).read()
    mods = set(re.findall(r"^\s*import (\w+)", src, re.M)) | set(re.findall(r"^\s*from (\w+) import", src, re.M))
    return all(m in getattr(sys, "stdlib_module_names", {"argparse","json","sys","operator","dataclasses","re","os","typing","collections","__future__"}) for m in mods)
def p16():
    d = var(); d["transitions"][1]["guard"] = [{"key": "progress", "op": ">=", "value": 100},
                                               {"key": "role", "op": "==", "value": "admin"}]
    c1, o1, _ = run(d, "start", "finish", "--context", '{"progress": 100, "role": "guest"}')
    c2, o2, _ = run(d, "start", "finish", "--context", '{"progress": 100, "role": "admin"}')
    return re.search(r"state: running\b", o1) and re.search(r"state: done", o2)
def p17():
    d = var(); d["transitions"][0]["from"] = 5
    c, o, e = run(d); return c != 0 and notb(e)
def p18():
    d = var(); d["final"] = d["finals"] = [["done"]]
    c, o, e = run(d); return c != 0 and notb(e)
def p19():
    c, o, e = run(var(), "--context", "[1]"); return c != 0 and notb(e)
def p20():
    c, o, e = run(var(), "start"); return c == 0 and "history" in o.lower() or ("idle" in o and "running" in o and c == 0)

for i, f in enumerate([p01,p02,p03,p04,p05,p06,p07,p08,p09,p10,p11,p12,p13,p14,p15,p16,p17,p18,p19,p20], 1):
    probe(f"P{i:02d}", f)
print(json.dumps(res))
