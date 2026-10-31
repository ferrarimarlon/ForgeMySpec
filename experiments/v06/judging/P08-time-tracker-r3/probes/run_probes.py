import ast, json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(side, f, *args):
    r = subprocess.run([sys.executable, os.path.join(ROOT, side, "time_tracker.py"), "--file", f, *args],
                       capture_output=True, text=True, timeout=20, cwd=tempfile.gettempdir(),
                       env={**os.environ, "HOME": tempfile.gettempdir()})
    return r.returncode, r.stdout + r.stderr
def seed(f, sessions):
    with open(f, "w") as fh: json.dump({"sessions": sessions}, fh)
def S(p, s, e): return {"project": p, "start": s, "end": e}
def sessions_of(f):
    d = json.load(open(f)); return d["sessions"] if isinstance(d, dict) else d
def probes(side):
    res = {}
    def P(pid, fn):
        d = tempfile.mkdtemp(); f = os.path.join(d, "data.json")
        try: ok = bool(fn(f))
        except Exception as e: ok = False; print(side, pid, "EXC", e)
        res[pid] = "pass" if ok else "fail"
    def p1(f):
        c, o = run(side, f, "start", "alpha"); s = sessions_of(f)
        return c == 0 and len(s) == 1 and s[0]["project"] == "alpha"
    def p2(f):
        run(side, f, "start", "alpha"); c, o = run(side, f, "start", "beta")
        return c != 0 and len(sessions_of(f)) == 1 and "Traceback" not in o
    def p3(f):
        run(side, f, "start", "alpha"); c, o = run(side, f, "stop"); s = sessions_of(f)
        return c == 0 and s[0].get("end") and "00:00:0" in o
    def p4(f):
        c, o = run(side, f, "stop"); return c != 0 and "Traceback" not in o
    def p5(f):
        seed(f, [S("alpha", "2026-01-01T10:00:00", "2026-01-01T11:02:03")])
        c, o = run(side, f, "log"); return c == 0 and "alpha" in o and "01:02:03" in o
    def p6(f):
        seed(f, [S("a", "2026-01-01T10:00:00", "2026-01-01T11:00:00"),
                 S("b", "2026-01-01T12:00:00", "2026-01-01T12:00:45"),
                 S("a", "2026-01-01T13:00:00", "2026-01-01T13:30:00")])
        c, o = run(side, f, "report")
        la = [l for l in o.splitlines() if l.split() and l.split()[0] == "a"]
        lb = [l for l in o.splitlines() if l.split() and l.split()[0] == "b"]
        return c == 0 and la and "01:30:00" in la[0] and lb and "00:00:45" in lb[0]
    def p7(f):
        seed(f, [S("a", "2026-01-01T10:00:00", "2026-01-01T11:00:00"),
                 S("b", "2026-01-01T10:30:00", "2026-01-01T12:00:00")])
        c, o = run(side, f, "log"); return c == 0 and "overlap" in o.lower()
    def p8(f):
        seed(f, [S("a", "2026-01-01T10:00:00", "2026-01-01T11:00:00"),
                 S("b", "2026-01-01T11:00:00", "2026-01-01T12:00:00")])
        c, o = run(side, f, "log"); return c == 0 and "overlap" not in o.lower()
    def p9(f):
        open(f, "w").write("{not json")
        c, o = run(side, f, "log"); return c != 0 and "Traceback" not in o
    def p10(f):
        seed(f, [S("long", "2026-01-01T00:00:00", "2026-01-02T01:00:05")])
        c, o = run(side, f, "report"); return c == 0 and "25:00:05" in o
    def p11(f):
        run(side, f, "start", "persist"); c, o = run(side, f, "log")
        return c == 0 and "persist" in o and "active" in o.lower()
    def p12(f):
        run(side, f, "start", "x"); run(side, f, "stop"); c, o = run(side, f, "start", "y")
        s = sessions_of(f); return c == 0 and len(s) == 2
    def p13(f):
        tree = ast.parse(open(os.path.join(ROOT, side, "time_tracker.py")).read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
        return mods <= {"argparse","json","os","sys","tempfile","datetime","collections"}
    def p14(f):
        seed(f, [S("a", "2020-01-01T10:00:00", "2099-01-01T10:00:00")])
        c, o = run(side, f, "start", "b")
        if c != 0 and "Traceback" not in o: return True
        c, o = run(side, f, "log"); return "overlap" in o.lower()
    def p15(f):
        c, o = run(side, f, "report"); return c == 0 and "Traceback" not in o
    def p16(f):
        open(f, "w").write('{"sessions": [{"start": "2026-01-01T10:00:00"}]}')
        c, o = run(side, f, "report"); return c != 0 and "Traceback" not in o
    for pid, fn in [("P01_start_persists", p1), ("P02_refuse_double_start", p2), ("P03_stop", p3),
                    ("P04_stop_no_active", p4), ("P05_log_hhmmss", p5), ("P06_report_totals", p6),
                    ("P07_overlap_detected", p7), ("P08_adjacent_not_overlap", p8),
                    ("P09_corrupt_json", p9), ("P10_over_24h", p10), ("P11_persist_across_procs", p11),
                    ("P12_start_after_stop", p12), ("P13_stdlib_only", p13),
                    ("P14_overlap_with_new_session", p14), ("P15_empty_report", p15),
                    ("P16_missing_field", p16)]:
        P(pid, fn)
    return res
out = {"A": probes("A"), "B": probes("B")}
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
