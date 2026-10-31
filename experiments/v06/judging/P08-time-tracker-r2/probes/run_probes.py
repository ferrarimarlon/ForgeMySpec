import json, os, re, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HMS = re.compile(r"\b\d{2,}:\d{2}:\d{2}\b")

def run(side, args, d):
    env = dict(os.environ, HOME=d, TIME_TRACKER_FILE=os.path.join(d, "tt.json"))
    p = subprocess.run([sys.executable, os.path.join(ROOT, side, "time_tracker.py")] + args,
                       cwd=d, env=env, capture_output=True, text=True, timeout=20)
    return p.returncode, p.stdout, p.stderr

def seed(d, sessions):
    with open(os.path.join(d, "tt.json"), "w") as f:
        json.dump({"sessions": sessions}, f)

def S(p, a, b): return {"project": p, "start": a, "end": b}

def probes(side):
    res, detail = {}, {}
    def P(pid, fn):
        with tempfile.TemporaryDirectory() as d:
            try:
                ok, info = fn(d)
            except Exception as e:
                ok, info = False, repr(e)
        res[pid] = "pass" if ok else "fail"; detail[pid] = info
    def p01(d):
        src = open(os.path.join(ROOT, side, "time_tracker.py")).read()
        mods = set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_]+)", src, re.M))
        bad = mods - {"argparse","json","os","sys","tempfile","datetime","re","time","pathlib","typing","collections","shutil"}
        return not bad, sorted(mods)
    P("P01_stdlib_only", p01)
    def p02(d):
        c, o, e = run(side, ["start", "alpha"], d)
        data = json.load(open(os.path.join(d, "tt.json")))
        return c == 0 and data["sessions"][0]["project"] == "alpha", (c, o, e)
    P("P02_start_persists_json", p02)
    def p03(d):
        run(side, ["start", "alpha"], d); time.sleep(1.2)
        c, o, e = run(side, ["stop"], d)
        data = json.load(open(os.path.join(d, "tt.json")))
        s = data["sessions"][0]
        return c == 0 and s.get("end") and HMS.search(o), (c, o, e)
    P("P03_stop_ends_and_shows_hms", p03)
    def p04(d):
        run(side, ["start", "alpha"], d)
        before = open(os.path.join(d, "tt.json")).read()
        c, o, e = run(side, ["start", "beta"], d)
        after = open(os.path.join(d, "tt.json")).read()
        return c != 0 and before == after and "Traceback" not in e, (c, o, e)
    P("P04_refuse_start_while_active", p04)
    def p05(d):
        c, o, e = run(side, ["stop"], d)
        return c != 0 and "Traceback" not in e, (c, o, e)
    P("P05_stop_without_active_errors", p05)
    def p06(d):
        seed(d, [S("a", "2026-01-01T09:00:00", "2026-01-01T10:00:00"),
                 S("b", "2026-01-01T10:00:00", "2026-01-01T10:10:00"),
                 S("a", "2026-01-01T11:00:00", "2026-01-01T11:30:30")])
        c, o, e = run(side, ["report"], d)
        la = [l for l in o.splitlines() if re.match(r"\s*a\s", l)]
        lb = [l for l in o.splitlines() if re.match(r"\s*b\s", l)]
        return c == 0 and la and "01:30:30" in la[0] and lb and "00:10:00" in lb[0], (c, o, e)
    P("P06_report_totals_per_project", p06)
    def p07(d):
        seed(d, [S("a", "2026-01-01T09:00:00", "2026-01-01T10:00:00"),
                 S("b", "2026-01-01T09:30:00", "2026-01-01T11:00:00")])
        c, o, e = run(side, ["log"], d)
        return c == 0 and "overlap" in (o + e).lower(), (c, o, e)
    P("P07_log_detects_overlap", p07)
    def p08(d):
        seed(d, [S("a", "2026-01-01T09:00:00", "2026-01-01T10:00:00"),
                 S("b", "2026-01-01T10:00:00", "2026-01-01T11:00:00")])
        c, o, e = run(side, ["log"], d)
        return c == 0 and "overlap" not in (o + e).lower(), (c, o, e)
    P("P08_no_false_overlap_adjacent", p08)
    def p09(d):
        seed(d, [S("a", "2026-01-01T09:00:00", "2026-01-01T10:00:00"),
                 S("b", "2026-01-01T09:30:00", "2026-01-01T11:00:00")])
        c, o, e = run(side, ["report"], d)
        return c == 0 and "overlap" in (o + e).lower(), (c, o, e)
    P("P09_report_flags_overlap", p09)
    def p10(d):
        seed(d, [S("a", "2026-01-01T09:00:00", "2026-01-01T10:01:05")])
        c, o, e = run(side, ["log"], d)
        return c == 0 and "01:01:05" in o and "a" in o, (c, o, e)
    P("P10_log_lists_session_hms", p10)
    def p11(d):
        seed(d, [S("a", "2026-01-01T00:00:00", "2026-01-05T04:00:00")])
        c, o, e = run(side, ["report"], d)
        return c == 0 and "100:00:00" in o, (c, o, e)
    P("P11_hms_over_24h", p11)
    def p12(d):
        open(os.path.join(d, "tt.json"), "w").write("{not json")
        c, o, e = run(side, ["log"], d)
        return c != 0 and "Traceback" not in e, (c, o, e[-300:])
    P("P12_corrupt_json_graceful", p12)
    def p13(d):
        c, o, e = run(side, ["start"], d)
        return c != 0 and "Traceback" not in e, (c, o, e)
    P("P13_start_missing_project", p13)
    def p14(d):
        run(side, ["start", "alpha"], d); time.sleep(1.1); run(side, ["stop"], d)
        run(side, ["start", "beta"], d); time.sleep(1.1); run(side, ["stop"], d)
        c, o, e = run(side, ["report"], d)
        c2, o2, e2 = run(side, ["log"], d)
        return c == 0 and "alpha" in o and "beta" in o and c2 == 0 and "overlap" not in (o2 + o).lower(), (o, o2, e, e2)
    P("P14_full_cycle_roundtrip", p14)
    def p15(d):
        c, o, e = run(side, ["start", "  "], d)
        return c != 0, (c, o, e)
    P("P15_reject_blank_project", p15)
    def p16(d):
        c, o, e = run(side, ["report"], d)
        return c == 0 and "Traceback" not in e, (c, o, e)
    P("P16_report_empty_ok", p16)
    return res, detail

if __name__ == "__main__":
    out, det = {}, {}
    for side in ("A", "B"):
        out[side], det[side] = probes(side)
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1)
    json.dump(det, open(os.path.join(HERE, "details.json"), "w"), indent=1, default=str)
    print(json.dumps(out, indent=1))
