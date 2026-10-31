"""Black-box probes. Usage: python3 run_probes.py <side_dir>  -> prints JSON {probe: pass|fail}"""
import json, os, subprocess, sys, tempfile, re

side = os.path.abspath(sys.argv[1])
prog = os.path.join(side, "expense_splitter.py")
results = {}
STDLIB = set(getattr(sys, 'stdlib_module_names', ())) or {'argparse','heapq','json','os','sys','tempfile','decimal','re','math','collections','pathlib','typing','dataclasses','datetime','fractions','uuid','shutil','itertools','functools','__future__'}

def run(args, cwd):
    if not os.path.exists(prog):
        return None
    return subprocess.run([sys.executable, "-I", prog, "-f", os.path.join(cwd, "e.json")] + args,
                          cwd=cwd, capture_output=True, text=True, timeout=20)

def add(cwd, payer, amount, desc, parts):
    return run(["add", "--payer", payer, "--amount", amount, "--description", desc, "--participants", *parts], cwd)

def probe(pid):
    def deco(fn):
        d = tempfile.mkdtemp()
        try:
            results[pid] = "pass" if fn(d) else "fail"
        except Exception as e:
            results[pid] = "fail"
        return fn
    return deco

def nums(text):
    return {m.group(1): float(m.group(2)) for m in re.finditer(r"^\s*(\w+)\D*?(-?\d+\.\d{2})", text, re.M)}

@probe("P01_file_exists_single_stdlib")
def _(d):
    if not os.path.exists(prog): return False
    src = open(prog).read()
    mods = set(re.findall(r"^\s*(?:import|from)\s+(\w+)", src, re.M))
    return mods <= STDLIB and len([f for f in os.listdir(side) if f.endswith(".py")]) == 1

@probe("P02_add_and_persist")
def _(d):
    r = add(d, "Alice", "30", "Dinner", ["Alice", "Bob", "Carol"])
    if r is None or r.returncode != 0: return False
    data = json.load(open(os.path.join(d, "e.json")))
    s = json.dumps(data)
    return "Alice" in s and "Dinner" in s and "Bob" in s and "Carol" in s

@probe("P03_balances_equal_split")
def _(d):
    add(d, "Alice", "30", "Dinner", ["Alice", "Bob", "Carol"])
    r = run(["balances"], d)
    if r is None or r.returncode != 0: return False
    n = nums(r.stdout)
    return n.get("Alice") == 20.0 and n.get("Bob") == -10.0 and n.get("Carol") == -10.0

@probe("P04_persist_across_runs")
def _(d):
    add(d, "Alice", "30", "Dinner", ["Alice", "Bob", "Carol"])
    add(d, "Bob", "60", "Hotel", ["Alice", "Bob", "Carol"])
    r = run(["balances"], d)
    n = nums(r.stdout)
    return n.get("Alice") == 0.0 and n.get("Bob") == 30.0 and n.get("Carol") == -30.0

@probe("P05_settle_greedy_min")
def _(d):
    # A owes 30, B owes 20 ... D paid 100 split among A,B,C,D,E
    add(d, "Dan", "100", "Trip", ["Ann", "Ben", "Cat", "Dan", "Eve"])
    add(d, "Cat", "50", "Food", ["Ann", "Ben", "Cat", "Dan", "Eve"])
    r = run(["settle"], d)
    if r is None or r.returncode != 0: return False
    lines = [l for l in r.stdout.splitlines() if re.search(r"\d+\.\d{2}", l) and "transfer" not in l.lower()]
    # balances: Dan +70, Cat +20, Ann -30, Ben -30, Eve -30 -> min 4 transfers
    total = sum(float(re.search(r"(\d+\.\d{2})", l).group(1)) for l in lines)
    return len(lines) == 4 and abs(total - 90) < 1e-9

@probe("P06_rounding_exact")
def _(d):
    add(d, "Alice", "10", "Taxi", ["Alice", "Bob", "Carol"])
    r = run(["balances"], d)
    n = nums(r.stdout)
    s = run(["settle"], d)
    amts = [float(x) for x in re.findall(r"(\d+\.\d{2})", s.stdout)]
    return abs(sum(n.values())) < 1e-9 and abs(sum(amts) - (n["Alice"])) < 1e-9

@probe("P07_payer_not_participant")
def _(d):
    add(d, "Alice", "20", "Gift", ["Bob", "Carol"])
    n = nums(run(["balances"], d).stdout)
    return n.get("Alice") == 20.0 and n.get("Bob") == -10.0

@probe("P08_reject_negative_amount")
def _(d):
    r = add(d, "Alice", "-5", "x", ["Bob"])
    return r is not None and r.returncode != 0 and "Traceback" not in r.stderr and not os.path.exists(os.path.join(d, "e.json"))

@probe("P09_reject_nonnumeric_amount")
def _(d):
    r = add(d, "Alice", "abc", "x", ["Bob"])
    return r is not None and r.returncode != 0 and "Traceback" not in r.stderr

@probe("P10_reject_nan_inf")
def _(d):
    r1 = add(d, "Alice", "nan", "x", ["Bob"]); r2 = add(d, "Alice", "inf", "x", ["Bob"])
    return r1 is not None and r1.returncode != 0 and r2.returncode != 0 and "Traceback" not in r1.stderr + r2.stderr

@probe("P11_corrupt_json_clean_error")
def _(d):
    if not os.path.exists(prog): return False
    open(os.path.join(d, "e.json"), "w").write("{not json")
    r = run(["balances"], d)
    return r.returncode != 0 and "Traceback" not in r.stderr

@probe("P12_malformed_record_clean_error")
def _(d):
    if not os.path.exists(prog): return False
    open(os.path.join(d, "e.json"), "w").write('[{"payer": "A"}]')
    r = run(["balances"], d)
    return r.returncode != 0 and "Traceback" not in r.stderr

@probe("P13_empty_state")
def _(d):
    r = run(["settle"], d)
    return r is not None and r.returncode == 0 and "Traceback" not in r.stderr

@probe("P14_settled_after_settlement")
def _(d):
    add(d, "Alice", "30", "Dinner", ["Alice", "Bob", "Carol"])
    s = run(["settle"], d)
    for l in s.stdout.splitlines():
        m = re.match(r"(\w+) pays (\w+) (\d+\.\d{2})", l)
        if m:
            add(d, m.group(1), m.group(3), "settle", [m.group(2)])
    s2 = run(["settle"], d)
    return s2.returncode == 0 and not re.search(r"\d+\.\d{2}", s2.stdout)

print(json.dumps(results))
