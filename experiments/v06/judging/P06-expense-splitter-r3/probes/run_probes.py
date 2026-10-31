import json, os, subprocess, sys, tempfile, ast
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Interface adapters: only invocation differs
IFACE = {
 "A": {"desc": "--desc", "parts": "--with"},
 "B": {"desc": "--description", "parts": "--participants"},
}

def run(side, d, *args):
    script = os.path.join(ROOT, side, "expense_splitter.py")
    f = os.path.join(d, "data.json")
    p = subprocess.run([sys.executable, "-I", script, "--file", f, *args],
                       capture_output=True, text=True, cwd=d, timeout=30)
    return p

def add(side, d, payer, amount, desc, parts):
    i = IFACE[side]
    return run(side, d, "add", "--payer", payer, "--amount", amount, i["desc"], desc, i["parts"], *parts)

def parse_balances(out):
    import re
    res = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\w+)\s*:?\s+(-?\d+\.\d\d)", line)
        if m: res[m.group(1)] = m.group(2)
    return res

def parse_settle(out):
    import re
    return [(m.group(1), m.group(2), m.group(3)) for m in
            re.finditer(r"(\w+) pays (\w+) (\d+\.\d\d)", out)]

def P_add_persist(side, d):
    p = add(side, d, "Alice", "60", "Dinner", ["Alice", "Bob", "Carol"])
    if p.returncode != 0: return False
    data = json.load(open(os.path.join(d, "data.json")))
    s = json.dumps(data)
    return "Alice" in s and "Dinner" in s and "Bob" in s and "Carol" in s

def P_balances_equal_split(side, d):
    add(side, d, "Alice", "60", "Dinner", ["Alice", "Bob", "Carol"])
    b = parse_balances(run(side, d, "balances").stdout)
    return b == {"Alice": "40.00", "Bob": "-20.00", "Carol": "-20.00"}

def P_persist_across_runs(side, d):
    add(side, d, "Alice", "30", "x", ["Alice", "Bob"])
    add(side, d, "Bob", "10", "y", ["Alice", "Bob"])
    b = parse_balances(run(side, d, "balances").stdout)
    return b == {"Alice": "10.00", "Bob": "-10.00"}

def P_rounding_sum_zero(side, d):
    add(side, d, "Alice", "10", "x", ["Alice", "Bob", "Carol"])
    b = parse_balances(run(side, d, "balances").stdout)
    cents = [round(float(v)*100) for v in b.values()]
    return len(b) == 3 and sum(cents) == 0

def P_payer_not_participant(side, d):
    add(side, d, "Dan", "20", "gift", ["Alice", "Bob"])
    b = parse_balances(run(side, d, "balances").stdout)
    return b == {"Alice": "-10.00", "Bob": "-10.00", "Dan": "20.00"}

def P_settle_basic(side, d):
    add(side, d, "Alice", "60", "Dinner", ["Alice", "Bob", "Carol"])
    t = parse_settle(run(side, d, "settle").stdout)
    return sorted(t) == [("Bob", "Alice", "20.00"), ("Carol", "Alice", "20.00")]

def P_settle_min_transfers(side, d):
    # A +30, B +10, C -20, D -20 -> greedy yields 3 transfers
    add(side, d, "A1", "40", "x", ["A1", "C1", "D1", "B1"])  # A1 +30, others -10
    add(side, d, "B1", "20", "y", ["C1", "D1"])            # B1 +20-10=+10, C1 -20, D1 -20
    out = run(side, d, "settle").stdout
    t = parse_settle(out)
    bal = {}
    for a, b, amt in t:
        c = round(float(amt)*100)
        bal[a] = bal.get(a, 0) + c; bal[b] = bal.get(b, 0) - c
    target = {"A1": -3000, "B1": -1000, "C1": 2000, "D1": 2000}
    return len(t) == 3 and all(bal.get(k, 0) == v for k, v in target.items())

def P_settle_exact_pair(side, d):
    # Greedy largest-first: A +50, B +20, C -50, D -20 -> 2 transfers
    add(side, d, "PA", "50", "x", ["PC"])
    add(side, d, "PB", "20", "y", ["PD"])
    t = parse_settle(run(side, d, "settle").stdout)
    return sorted(t) == [("PC", "PA", "50.00"), ("PD", "PB", "20.00")]

def P_settle_after_settled(side, d):
    add(side, d, "Alice", "10", "x", ["Bob"])
    add(side, d, "Bob", "10", "y", ["Alice"])
    p = run(side, d, "settle")
    return p.returncode == 0 and parse_settle(p.stdout) == []

def P_reject_negative(side, d):
    p = add(side, d, "Alice", "-5", "x", ["Alice", "Bob"])
    return p.returncode != 0 and "Traceback" not in p.stderr and not os.path.exists(os.path.join(d, "data.json"))

def P_reject_zero(side, d):
    p = add(side, d, "Alice", "0", "x", ["Alice", "Bob"])
    return p.returncode != 0 and "Traceback" not in p.stderr

def P_reject_nonnumeric(side, d):
    p = add(side, d, "Alice", "abc", "x", ["Alice", "Bob"])
    return p.returncode != 0 and "Traceback" not in p.stderr

def P_reject_nan_inf(side, d):
    r = [add(side, d, "Alice", v, "x", ["Alice"]) for v in ("nan", "inf")]
    return all(p.returncode != 0 and "Traceback" not in p.stderr for p in r)

def P_reject_missing_participants(side, d):
    i = IFACE[side]
    p = run(side, d, "add", "--payer", "Alice", "--amount", "5", i["desc"], "x")
    return p.returncode != 0 and "Traceback" not in p.stderr

def P_reject_empty_payer(side, d):
    p = add(side, d, "  ", "5", "x", ["Alice"])
    return p.returncode != 0 and "Traceback" not in p.stderr

def P_decimal_amount(side, d):
    add(side, d, "Alice", "12.34", "x", ["Alice", "Bob"])
    b = parse_balances(run(side, d, "balances").stdout)
    return b == {"Alice": "6.17", "Bob": "-6.17"}

def P_corrupt_json(side, d):
    open(os.path.join(d, "data.json"), "w").write("{not json")
    p = run(side, d, "balances")
    return p.returncode != 0 and "Traceback" not in p.stderr

def P_wrong_shape_json(side, d):
    open(os.path.join(d, "data.json"), "w").write('{"expenses": [{"payer": "A", "amount_cents": 100, "description": "x", "participants": [1, 2]}]}')
    p = run(side, d, "settle")
    q = run(side, d, "balances")
    return all("Traceback" not in r.stderr for r in (p, q))

def P_file_is_directory(side, d):
    os.mkdir(os.path.join(d, "data.json"))
    p = run(side, d, "balances")
    return p.returncode != 0 and "Traceback" not in p.stderr

def P_missing_file_empty(side, d):
    p = run(side, d, "settle")
    return p.returncode == 0 and "Traceback" not in p.stderr

def P_corrupt_not_overwritten(side, d):
    f = os.path.join(d, "data.json"); open(f, "w").write("garbage")
    add(side, d, "Alice", "5", "x", ["Alice", "Bob"])
    return open(f).read() == "garbage"

def P_stdlib_only(side, d):
    src = open(os.path.join(ROOT, side, "expense_splitter.py")).read()
    tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    std = set(getattr(sys, "stdlib_module_names", ())) or {"argparse","heapq","json","os","sys","tempfile","decimal"}
    return mods <= std

def P_single_file(side, d):
    py = [f for f in os.listdir(os.path.join(ROOT, side)) if f.endswith(".py")]
    return py == ["expense_splitter.py"]

def P_default_file_cwd(side, d):
    i = IFACE[side]
    script = os.path.join(ROOT, side, "expense_splitter.py")
    p = subprocess.run([sys.executable, "-I", script, "add", "--payer", "A", "--amount", "1", i["desc"], "x", i["parts"], "A", "B"],
                       capture_output=True, text=True, cwd=d)
    return p.returncode == 0 and any(f.endswith(".json") for f in os.listdir(d))

PROBES = {k: v for k, v in globals().items() if k.startswith("P_")}

results = {}
for side in ("A", "B"):
    results[side] = {}
    for name, fn in PROBES.items():
        with tempfile.TemporaryDirectory() as d:
            try: ok = fn(side, d)
            except Exception as e: ok = False; print(side, name, "EXC", e)
        results[side][name[2:]] = "pass" if ok else "fail"
json.dump(results, open(os.path.join(HERE, "results.json"), "w"), indent=2)
for side in results:
    print(side, sum(v == "pass" for v in results[side].values()), "/", len(results[side]),
          [k for k, v in results[side].items() if v == "fail"])
