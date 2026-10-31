import json, os, subprocess, sys, tempfile, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDES = {
 "A": {"desc": "--desc", "parts": "--with"},
 "B": {"desc": "--description", "parts": "--participants"},
}
def run(side, d, *args):
    exe = os.path.join(ROOT, side, "expense_splitter.py")
    return subprocess.run([sys.executable, "-I", exe, "--file", os.path.join(d, "e.json"), *args],
                          capture_output=True, text=True, cwd=d, timeout=30)
def add(side, d, payer, amt, desc, parts):
    s = SIDES[side]
    return run(side, d, "add", "--payer", payer, "--amount", amt, s["desc"], desc, s["parts"], *parts)
def bal(side, d):
    r = run(side, d, "balances"); out = {}
    for line in r.stdout.splitlines():
        m = re.match(r"\s*(\S+)\s*:\s*(-?\d+\.\d\d)", line)
        if m: out[m.group(1)] = m.group(2)
    return r, out
def transfers(side, d):
    r = run(side, d, "settle"); t = []
    for line in r.stdout.splitlines():
        m = re.match(r"(\S+) pays (\S+) (\d+\.\d\d)", line)
        if m: t.append((m.group(1), m.group(2), m.group(3)))
    return r, t
def clean(r): return "Traceback" not in r.stderr
P = {}
def probe(f): P[f.__name__] = f; return f

@probe
def p01_add_ok(side, d):
    r = add(side, d, "Alice", "30.00", "Dinner", ["Alice", "Bob", "Carol"])
    return r.returncode == 0 and os.path.exists(os.path.join(d, "e.json"))
@probe
def p02_persist_json(side, d):
    add(side, d, "Alice", "30.00", "Dinner", ["Alice", "Bob", "Carol"])
    txt = open(os.path.join(d, "e.json")).read(); json.loads(txt)
    return "Dinner" in txt and "Alice" in txt and "Bob" in txt
@probe
def p03_list_shows(side, d):
    add(side, d, "Alice", "30.00", "Dinner", ["Alice", "Bob", "Carol"])
    r = run(side, d, "list"); return r.returncode == 0 and "Dinner" in r.stdout and "30.00" in r.stdout
@probe
def p04_equal_balances(side, d):
    add(side, d, "Alice", "30.00", "Dinner", ["Alice", "Bob", "Carol"])
    _, b = bal(side, d); return b == {"Alice": "20.00", "Bob": "-10.00", "Carol": "-10.00"}
@probe
def p05_multi_persist(side, d):
    add(side, d, "Alice", "30.00", "Dinner", ["Alice", "Bob", "Carol"])
    add(side, d, "Bob", "60.00", "Taxi", ["Alice", "Bob", "Carol"])
    _, b = bal(side, d); return b == {"Alice": "0.00", "Bob": "30.00", "Carol": "-30.00"}
@probe
def p06_uneven_sum_zero(side, d):
    add(side, d, "Alice", "10.00", "x", ["Alice", "Bob", "Carol"])
    _, b = bal(side, d)
    s = sum(round(float(v)*100) for v in b.values())
    return s == 0 and len(b) == 3
@probe
def p07_payer_not_participant(side, d):
    add(side, d, "Alice", "20.00", "x", ["Bob", "Carol"])
    _, b = bal(side, d); return b == {"Alice": "20.00", "Bob": "-10.00", "Carol": "-10.00"}
@probe
def p08_settle_simple(side, d):
    add(side, d, "Alice", "30.00", "Dinner", ["Alice", "Bob", "Carol"])
    _, t = transfers(side, d)
    return sorted(t) == [("Bob", "Alice", "10.00"), ("Carol", "Alice", "10.00")]
@probe
def p09_settle_min_transfers(side, d):
    # A owed 40, B owed 20, C owes 30, D owes 30 -> greedy gives 3 transfers
    add(side, d, "A1", "80.00", "x", ["A1", "C1", "D1", "B1"])
    add(side, d, "B1", "40.00", "y", ["B1", "C1", "D1", "A1"])
    # bal: A1 80-30=50, B1 40-30=10, C1 -30, D1 -30
    _, t = transfers(side, d)
    net = {}
    for a, b, v in t:
        c = round(float(v)*100); net[a] = net.get(a, 0) - c; net[b] = net.get(b, 0) + c
    return len(t) <= 3 and net == {"A1": 5000, "B1": 1000, "C1": -3000, "D1": -3000}
@probe
def p10_settle_zeroes_all(side, d):
    add(side, d, "Alice", "10.00", "x", ["Alice", "Bob", "Carol"])
    add(side, d, "Bob", "7.33", "y", ["Alice", "Carol", "Dan"])
    add(side, d, "Dan", "100.01", "z", ["Alice", "Bob", "Carol", "Dan", "Eve"])
    _, b = bal(side, d); _, t = transfers(side, d)
    cents = {k: round(float(v)*100) for k, v in b.items()}
    for a, c, v in t:
        x = round(float(v)*100); cents[a] += x; cents[c] -= x
    nz = sum(1 for v in b.values() if float(v) != 0)
    return all(v == 0 for v in cents.values()) and len(t) <= nz - 1
@probe
def p11_settled_message(side, d):
    add(side, d, "Alice", "10.00", "x", ["Alice"])
    r, t = transfers(side, d); return r.returncode == 0 and t == []
@probe
def p12_reject_negative(side, d):
    r = add(side, d, "Alice", "-5", "x", ["Alice", "Bob"])
    return r.returncode != 0 and clean(r) and not os.path.exists(os.path.join(d, "e.json"))
@probe
def p13_reject_zero(side, d):
    r = add(side, d, "Alice", "0", "x", ["Alice", "Bob"]); return r.returncode != 0 and clean(r)
@probe
def p14_reject_nonnumeric(side, d):
    r = add(side, d, "Alice", "abc", "x", ["Alice", "Bob"]); return r.returncode != 0 and clean(r)
@probe
def p15_reject_nan_inf(side, d):
    rs = [add(side, d, "Alice", v, "x", ["Alice", "Bob"]) for v in ("nan", "inf")]
    return all(r.returncode != 0 and clean(r) for r in rs)
@probe
def p16_reject_subcent(side, d):
    r = add(side, d, "Alice", "1.005", "x", ["Alice", "Bob"]); return r.returncode != 0 and clean(r)
@probe
def p17_reject_empty_payer(side, d):
    r = add(side, d, "  ", "5", "x", ["Alice", "Bob"]); return r.returncode != 0 and clean(r)
@probe
def p18_reject_missing_participants(side, d):
    r = add(side, d, "Alice", "5", "x", []); return r.returncode != 0 and clean(r)
@probe
def p19_corrupt_json(side, d):
    open(os.path.join(d, "e.json"), "w").write("{not json")
    r = run(side, d, "balances"); return r.returncode != 0 and clean(r)
@probe
def p20_wrong_shape_json(side, d):
    open(os.path.join(d, "e.json"), "w").write('[{"payer": "a"}]' if side == "A" else '{"expenses": [{"payer": "a"}]}')
    r = run(side, d, "balances"); return r.returncode != 0 and clean(r)
@probe
def p21_missing_file_empty(side, d):
    r = run(side, d, "balances"); r2 = run(side, d, "settle")
    return r.returncode == 0 and r2.returncode == 0 and clean(r) and clean(r2)
@probe
def p22_corrupt_not_overwritten(side, d):
    open(os.path.join(d, "e.json"), "w").write("{not json")
    r = add(side, d, "Alice", "5", "x", ["Alice", "Bob"])
    return r.returncode != 0 and open(os.path.join(d, "e.json")).read() == "{not json"
@probe
def p23_float_precision(side, d):
    for _ in range(10): add(side, d, "Alice", "0.10", "x", ["Alice", "Bob"])
    _, b = bal(side, d); return b == {"Alice": "0.50", "Bob": "-0.50"}
@probe
def p24_unicode_desc(side, d):
    add(side, d, "José", "12.50", "Café ☕", ["José", "Zoë"])
    r = run(side, d, "list"); return r.returncode == 0 and "Café ☕" in r.stdout
@probe
def p25_dup_participant(side, d):
    add(side, d, "Alice", "20.00", "x", ["Alice", "Bob", "Bob"])
    _, b = bal(side, d); return b == {"Alice": "10.00", "Bob": "-10.00"}
@probe
def p26_stdlib_single_file(side, d):
    src = open(os.path.join(ROOT, side, "expense_splitter.py")).read()
    mods = set(re.findall(r"^\s*(?:import|from)\s+(\w+)", src, re.M))
    return mods <= set(sys.stdlib_module_names)
@probe
def p27_help(side, d):
    r = run(side, d, "--help"); return r.returncode == 0 and "add" in r.stdout

res = {}
for side in ("A", "B"):
    res[side] = {}
    for name, f in P.items():
        with tempfile.TemporaryDirectory() as d:
            try: ok = f(side, d)
            except Exception as e: ok = False; print(side, name, "EXC", e)
        res[side][name] = "pass" if ok else "fail"
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for side in res:
    print(side, sum(v == "pass" for v in res[side].values()), "/", len(P), [k for k, v in res[side].items() if v == "fail"])
