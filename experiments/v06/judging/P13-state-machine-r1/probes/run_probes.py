import json, os, subprocess, sys, tempfile, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def adapter(side, mode, mfile, events=(), context=None):
    script = os.path.join(ROOT, side, "state_machine.py")
    if side == "A":
        if mode == "validate":
            cmd = [script, "validate", mfile]
        else:
            cmd = [script, "run", mfile, *events]
            if context is not None: cmd += ["--context", context]
    else:
        if mode == "validate":
            cmd = [script, mfile, "--validate"]
        else:
            cmd = [script, mfile, *events, "--history"]
            if context is not None: cmd += ["--context", context]
    return cmd

def run(side, mode, machine, events=(), context=None, raw=None):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "m.json")
    with open(p, "w") as f:
        f.write(raw if raw is not None else json.dumps(machine))
    cmd = adapter(side, mode, p, events, context)
    r = subprocess.run([sys.executable, "-I", *cmd], capture_output=True, text=True, cwd=d, timeout=20)
    return r.returncode, r.stdout + r.stderr

BASE = {"states": ["idle", "running", "done"], "initial": "idle", "final": ["done"],
        "transitions": [
            {"from": "idle", "event": "start", "to": "running"},
            {"from": "running", "event": "finish", "to": "done",
             "guard": {"key": "progress", "op": ">=", "value": 100}}]}

def mod(**kw):
    m = json.loads(json.dumps(BASE)); m.update(kw); return m

def notb(o): return "Traceback" not in o

def probes(side):
    res = {}
    rc, o = run(side, "validate", BASE); res["P01_valid_ok"] = rc == 0 and notb(o)
    m = mod(transitions=BASE["transitions"] + [{"from": "idle", "event": "x", "to": "ghost"}])
    rc, o = run(side, "validate", m); res["P02_unknown_state"] = rc != 0 and "ghost" in o and notb(o)
    m = mod(states=BASE["states"] + ["island"])
    rc, o = run(side, "validate", m); res["P03_unreachable"] = rc != 0 and "island" in o and "unreachable" in o.lower()
    m = mod(); del m["initial"]
    rc, o = run(side, "validate", m); res["P04_missing_initial"] = rc != 0 and "initial" in o.lower() and notb(o)
    m = mod(initial="nowhere")
    rc, o = run(side, "validate", m); res["P05_initial_not_in_states"] = rc != 0 and "nowhere" in o and notb(o)
    m = mod(final=["zzz"])
    rc, o = run(side, "validate", m); res["P06_unknown_final"] = rc != 0 and "zzz" in o and notb(o)
    rc, o = run(side, "run", BASE, ["start", "finish"], '{"progress": 100}')
    res["P07_guard_pass_reaches_final"] = rc == 0 and "done" in o.splitlines()[-1] if False else (rc == 0 and "running --finish--> done" in o)
    rc, o = run(side, "run", BASE, ["start", "finish"], '{"progress": 5}')
    res["P08_guard_fail_blocks"] = rc != 0 and "running --finish--> done" not in o and notb(o)
    rc, o = run(side, "run", BASE, ["bogus"])
    res["P09_unknown_event_reported"] = rc != 0 and "bogus" in o and notb(o)
    rc, o = run(side, "run", BASE, ["start", "finish"], '{"progress": 200}')
    i1, i2 = o.find("idle --start--> running"), o.find("running --finish--> done")
    res["P10_history_ordered"] = 0 <= i1 < i2
    rc, o = run(side, "run", BASE, ["start", "finish", "start"], '{"progress": 200}')
    res["P11_event_after_final_rejected"] = rc != 0 and "done --start--> running" not in o and notb(o)
    rc, o = run(side, "validate", None, raw="{not json"); res["P12_malformed_json"] = rc != 0 and notb(o)
    d = tempfile.mkdtemp(); script = os.path.join(ROOT, side, "state_machine.py")
    cmd = [script, "validate", d + "/missing.json"] if side == "A" else [script, d + "/missing.json", "--validate"]
    r = subprocess.run([sys.executable, "-I", *cmd], capture_output=True, text=True, cwd=d)
    res["P13_missing_file"] = r.returncode != 0 and notb(r.stdout + r.stderr)
    rc, o = run(side, "validate", [1, 2]); res["P14_toplevel_list"] = rc != 0 and notb(o)
    m = mod(transitions=[{"from": "idle", "event": "e", "to": ["running"]}])
    rc, o = run(side, "validate", m); res["P15_unhashable_state_ref"] = rc != 0 and notb(o)
    rc, o = run(side, "run", BASE, ["start"], "{bad"); res["P16_bad_context"] = rc != 0 and notb(o)
    sentinel = os.path.join(tempfile.mkdtemp(), "pwned")
    m = mod(transitions=[{"from": "idle", "event": "start", "to": "running",
                           "guard": f"__import__('os').system('touch {sentinel}')"},
                          {"from": "running", "event": "finish", "to": "done"}])
    rc, o = run(side, "run", m, ["start"])
    res["P17_guard_no_code_exec"] = not os.path.exists(sentinel) and notb(o)
    m = mod(transitions=[{"from": "idle", "event": "go", "to": "running", "guard": {"key": "n", "op": "==", "value": 1}},
                          {"from": "idle", "event": "go", "to": "done"},
                          {"from": "running", "event": "finish", "to": "done"}])
    rc, o = run(side, "run", m, ["go"], '{"n": 2}')
    res["P18_guard_fallthrough_next_transition"] = rc == 0 and "idle --go--> done" in o
    src = open(os.path.join(ROOT, side, "state_machine.py")).read()
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    res["P19_stdlib_only"] = mods <= {"argparse","json","operator","sys","os","re","typing","collections","dataclasses","pathlib"}
    res["P20_single_file"] = os.path.isfile(os.path.join(ROOT, side, "state_machine.py"))
    return {k: ("pass" if v else "fail") for k, v in res.items()}

out = {s: probes(s) for s in ("A", "B")}
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
