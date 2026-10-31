"""Black-box probes. Usage: python3 run_probes.py <side_dir>  -> prints JSON {probe: pass|fail}"""
import json, os, subprocess, sys, tempfile, re
side = os.path.abspath(sys.argv[1])
prog = os.path.join(side, "state_machine.py")
tmp = tempfile.mkdtemp()
def mk(name, obj, raw=None):
    p = os.path.join(tmp, name)
    with open(p, "w") as f:
        f.write(raw if raw is not None else json.dumps(obj))
    return p
def run(*args):
    if not os.path.exists(prog):
        return None
    r = subprocess.run([sys.executable, prog, *args], capture_output=True, text=True, cwd=tmp, timeout=20)
    return r
GOOD = {"initial": "idle", "states": ["idle", "running", "done"], "final": ["done"],
        "transitions": [{"from": "idle", "event": "start", "to": "running"},
                        {"from": "running", "event": "finish", "to": "done",
                         "guard": {"key": "ok", "op": "==", "value": True}}]}
good = mk("good.json", GOOD)
res = {}
def probe(pid, fn):
    try:
        res[pid] = "pass" if fn() else "fail"
    except Exception:
        res[pid] = "fail"
nt = lambda r: "Traceback" not in r.stderr + r.stdout
# P1 single file + stdlib
def p1():
    if not os.path.exists(prog): return False
    files = [f for f in os.listdir(side) if f.endswith(".py")]
    src = open(prog).read()
    imps = set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_]\w*)", src, re.M))
    STD = getattr(sys, "stdlib_module_names", None) or {"argparse","json","operator","sys","os","re","ast","collections","typing","dataclasses","pathlib","enum","functools","itertools","datetime","textwrap","copy","__future__","abc","shlex","logging"}
    return len(files) == 1 and all(i in STD for i in imps)
probe("P1_single_file_stdlib", p1)
probe("P2_validate_good", lambda: (r := run("validate", good)) and r.returncode == 0 and nt(r))
def p3():
    d = dict(GOOD); d["transitions"] = GOOD["transitions"] + [{"from": "idle", "event": "x", "to": "nowhere"}]
    r = run("validate", mk("unk.json", d)); return r.returncode != 0 and "nowhere" in (r.stdout + r.stderr) and nt(r)
probe("P3_unknown_target_state", p3)
def p3b():
    d = dict(GOOD); d["transitions"] = GOOD["transitions"] + [{"from": "ghost", "event": "x", "to": "idle"}]
    r = run("validate", mk("unk2.json", d)); return r.returncode != 0 and "ghost" in (r.stdout + r.stderr) and nt(r)
probe("P4_unknown_source_state", p3b)
def p4():
    d = dict(GOOD); d["states"] = GOOD["states"] + ["orphan"]
    r = run("validate", mk("unr.json", d)); o = (r.stdout + r.stderr).lower()
    return r.returncode != 0 and "orphan" in o and "unreachable" in o and nt(r)
probe("P5_unreachable_state", p4)
def p5():
    d = {k: v for k, v in GOOD.items() if k != "initial"}
    r = run("validate", mk("noinit.json", d)); return r.returncode != 0 and "initial" in (r.stdout + r.stderr).lower() and nt(r)
probe("P6_missing_initial", p5)
def p6():
    d = dict(GOOD); d["initial"] = "bogus"
    r = run("validate", mk("badinit.json", d)); return r.returncode != 0 and "bogus" in (r.stdout + r.stderr) and nt(r)
probe("P7_unknown_initial", p6)
def p7():
    d = dict(GOOD); d["final"] = ["zzz"]
    r = run("validate", mk("badfinal.json", d)); return r.returncode != 0 and "zzz" in (r.stdout + r.stderr) and nt(r)
probe("P8_unknown_final", p7)
probe("P9_run_events_guard_pass", lambda: (r := run("run", good, "start", "finish", "--context", '{"ok": true}')) and r.returncode == 0 and "done" in r.stdout)
def p10():
    r = run("run", good, "start", "finish", "--context", '{"ok": false}')
    return "running" in r.stdout and "done" not in r.stdout.split("final state")[-1].split("\n")[0] and nt(r)
probe("P10_guard_blocks", p10)
def p11():
    r = run("run", good, "start", "finish", "--context", '{"ok": true}', "--history")
    o = r.stdout; return "start" in o and "finish" in o and "idle" in o and "running" in o and o.index("start") < o.index("finish")
probe("P11_history_printed", p11)
def p12():
    r = run("run", good, "bogus_event"); return nt(r) and "idle" in r.stdout + r.stderr
probe("P12_unknown_event_no_crash", p12)
probe("P13_missing_file", lambda: (r := run("validate", os.path.join(tmp, "nope.json"))) and r.returncode != 0 and nt(r))
probe("P14_malformed_json", lambda: (r := run("validate", mk("bad.json", None, "{not json"))) and r.returncode != 0 and nt(r))
def p15():
    r = run("run", good, "start", "finish", "--context", '{"ok": true}'); return "final" in r.stdout.lower() and "done" in r.stdout
probe("P15_reports_final_state", p15)
def p16():
    d = dict(GOOD); d["transitions"] = [{"from": "idle", "event": "start", "to": "running",
        "guard": "__import__('os').system('touch PWNED')"}] + GOOD["transitions"][1:]
    if not os.path.exists(prog): return False
    pth = mk("inj.json", d); run("validate", pth); run("run", pth, "start")
    return not os.path.exists(os.path.join(tmp, "PWNED"))
probe("P16_guard_no_code_exec", p16)
def p17():
    d = dict(GOOD); d["final"] = [{"x": 1}]
    r = run("validate", mk("unhash.json", d)); return r.returncode != 0 and nt(r)
probe("P17_malformed_def_no_traceback", p17)
def p18():
    r = run("run", mk("unr2.json", dict(GOOD, states=GOOD["states"] + ["orphan"])), "start")
    return r.returncode != 0 and nt(r)
probe("P18_run_rejects_invalid_def", p18)
print(json.dumps(res))
