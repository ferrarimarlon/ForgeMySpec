import ast, json, os, subprocess, sys, tempfile
SIDE = sys.argv[1]; ROOT = os.path.abspath(SIDE); SCRIPT = os.path.join(ROOT, "time_tracker.py")
def run(path, *a):
    env = dict(os.environ); env.pop("TIME_TRACKER_FILE", None)
    p = subprocess.run([sys.executable, "-I", SCRIPT, "--file", path, *a], capture_output=True, text=True, cwd=os.path.dirname(path), env=env)
    return p.returncode, p.stdout, p.stderr
def seed(path, sessions):
    json.dump({"sessions": sessions}, open(path, "w"))
def S(p, s, e): return {"project": p, "start": s, "end": e}
def nt(r): return "Traceback" not in r[2]
res = {}
def probe(pid, fn):
    d = tempfile.mkdtemp(); path = os.path.join(d, "data.json")
    try: ok = bool(fn(path))
    except Exception as e: ok = False; print(pid, "EXC", e)
    res[pid] = "pass" if ok else "fail"
def p1(p):
    r = run(p, "start", "alpha"); d = json.load(open(p))
    return r[0] == 0 and "alpha" in json.dumps(d)
def p2(p):
    run(p, "start", "alpha"); r = run(p, "start", "beta"); d = json.dumps(json.load(open(p)))
    return r[0] != 0 and "beta" not in d and nt(r)
def p3(p):
    run(p, "start", "alpha"); r = run(p, "stop"); d = json.load(open(p))
    ss = d["sessions"] if isinstance(d, dict) else d
    return r[0] == 0 and all(s.get("end") for s in ss)
def p4(p):
    r = run(p, "stop"); return r[0] != 0 and nt(r)
def p5(p):
    seed(p, [S("alpha", "2026-01-01T09:00:00+00:00", "2026-01-01T10:01:02+00:00")])
    r = run(p, "log"); return r[0] == 0 and "alpha" in r[1] and "01:01:02" in r[1]
def p6(p):
    seed(p, [S("alpha", "2026-01-01T09:00:00+00:00", "2026-01-01T10:00:00+00:00"),
             S("beta", "2026-01-01T10:00:00+00:00", "2026-01-01T10:00:45+00:00"),
             S("alpha", "2026-01-01T11:00:00+00:00", "2026-01-01T11:30:00+00:00")])
    r = run(p, "report"); lines = r[1].splitlines()
    a = [l for l in lines if "alpha" in l]; b = [l for l in lines if "beta" in l]
    return r[0] == 0 and len(a) == 1 and "01:30:00" in a[0] and len(b) == 1 and "00:00:45" in b[0]
OV = [S("alpha", "2026-01-01T09:00:00+00:00", "2026-01-01T10:00:00+00:00"),
      S("beta", "2026-01-01T09:30:00+00:00", "2026-01-01T10:30:00+00:00")]
def p7(p):
    seed(p, OV); r = run(p, "log"); return r[0] == 0 and "overlap" in (r[1] + r[2]).lower()
def p8(p):
    seed(p, [S("alpha", "2026-01-01T09:00:00+00:00", "2026-01-01T10:00:00+00:00"),
             S("beta", "2026-01-01T10:00:00+00:00", "2026-01-01T11:00:00+00:00")])
    r = run(p, "log"); r2 = run(p, "report")
    return r[0] == 0 and "overlap" not in (r[1] + r[2] + r2[1] + r2[2]).lower()
def p9(p):
    open(p, "w").write("{not json"); r = run(p, "report"); return r[0] != 0 and nt(r)
def p10(p):
    seed(p, [S("alpha", "2026-01-01T00:00:00+00:00", "2026-01-02T01:00:00+00:00")])
    r = run(p, "report"); return r[0] == 0 and "25:00:00" in r[1]
def p11(p):
    files = [f for f in os.listdir(ROOT) if f.endswith(".py")]
    t = ast.parse(open(SCRIPT).read()); mods = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    return files == ["time_tracker.py"] and mods <= {"argparse","json","os","sys","tempfile","datetime"}
def p12(p):
    seed(p, [S("alpha", "not-a-date", None)]); r = run(p, "log"); return r[0] != 0 and nt(r)
def p13(p):
    seed(p, [S("alpha", "2026-01-01T09:00:00", "2026-01-01T10:00:00")]); r = run(p, "report"); return nt(r)
def p14(p):
    run(p, "start", "alpha"); r = run(p, "log"); return r[0] == 0 and "alpha" in r[1] and "active" in r[1].lower()
def p15(p):
    seed(p, OV); r = run(p, "report"); return r[0] == 0 and "01:00:00" in r[1]
for i, f in enumerate([p1,p2,p3,p4,p5,p6,p7,p8,p9,p10,p11,p12,p13,p14,p15], 1):
    probe(f"P{i}", f)
print(json.dumps(res))
