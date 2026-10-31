import json, subprocess, sys, tempfile, os, re, ast
SIDES = {"A": os.path.abspath("A/invoice_gen.py"), "B": os.path.abspath("B/invoice_gen.py")}
BASE = {"customer": {"name": "Acme Corp", "email": "a@acme.test"},
        "items": [{"description": "Widget", "quantity": 3, "unit_price": 9.99},
                  {"description": "Gadget", "quantity": 2, "unit_price": 5.00}],
        "tax_rate": 8.25, "discount": {"type": "percent", "value": 10}}

def run(prog, data, fmt=None, raw=None, path=None):
    d = tempfile.mkdtemp()
    p = path or os.path.join(d, "inv.json")
    if path is None:
        with open(p, "w") as f:
            f.write(raw if raw is not None else json.dumps(data))
    cmd = [sys.executable, "-I", prog, p] + (["--format", fmt] if fmt else [])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=d, timeout=20)
    return r

def vals_in(text, vals):
    return all(v in text for v in vals)

def jvals(obj):
    out = []
    def walk(o):
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
        else: out.append(str(o))
    walk(obj); return out

def p_single_stdlib(prog):
    src = open(prog).read(); tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split('.')[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.level == 0: mods.add(n.module.split('.')[0])
    STD = {"argparse","json","sys","decimal","datetime","os","re","io","math","pathlib","typing","dataclasses","collections","textwrap"}
    return all(m in STD for m in mods)

def p_text_basic(prog):
    r = run(prog, BASE)
    return r.returncode == 0 and vals_in(r.stdout, ["Acme Corp", "Widget", "29.97", "10.00", "39.97", "4.00", "2.97", "38.94"])

def p_json_basic(prog):
    r = run(prog, BASE, fmt="json")
    if r.returncode: return False
    o = json.loads(r.stdout); v = jvals(o)
    return all(x in v for x in ["29.97", "10.00", "39.97", "2.97", "38.94"]) and ("4.00" in v)

def p_no_discount(prog):
    d = dict(BASE); d.pop("discount")
    r = run(prog, d, fmt="json")
    if r.returncode: return False
    v = jvals(json.loads(r.stdout))
    # 39.97 * 8.25% = 3.297525 -> 3.30 ; total 43.27
    return all(x in v for x in ["39.97", "3.30", "43.27"])

def p_multi_errors(prog):
    d = {"customer": {"name": ""}, "items": [{"description": "", "quantity": -1, "unit_price": "x"}], "tax_rate": 150}
    r = run(prog, d)
    lines = [l for l in r.stderr.splitlines() if re.search(r"customer|description|quantity|unit_price|tax", l)]
    return r.returncode != 0 and r.stdout.strip() == "" and len(lines) >= 5 and "Traceback" not in r.stderr

def p_half_up_line(prog):
    d = {"customer": {"name": "X"}, "items": [{"description": "a", "quantity": 1, "unit_price": 0.125},
         {"description": "b", "quantity": 1, "unit_price": 0.1}, {"description": "c", "quantity": 1, "unit_price": 0.2}], "tax_rate": 0}
    r = run(prog, d, fmt="json")
    if r.returncode: return False
    v = jvals(json.loads(r.stdout))
    return "0.13" in v and "0.43" in v

def p_half_up_tax(prog):
    d = {"customer": {"name": "X"}, "items": [{"description": "a", "quantity": 1, "unit_price": 1.00}], "tax_rate": 12.5}
    r = run(prog, d, fmt="json")
    if r.returncode: return False
    v = jvals(json.loads(r.stdout))
    return "0.13" in v and "1.13" in v

def p_float_artifact(prog):
    d = {"customer": {"name": "X"}, "items": [{"description": "a", "quantity": 3, "unit_price": 1.1}], "tax_rate": 0}
    r = run(prog, d)
    return r.returncode == 0 and "3.30" in r.stdout and "3.3000000" not in r.stdout

def p_fixed_discount(prog):
    d = dict(BASE); d["discount"] = {"type": "fixed", "value": 5}
    r = run(prog, d, fmt="json")
    if r.returncode: return False
    v = jvals(json.loads(r.stdout))
    # taxable 34.97 tax 2.885025 -> 2.89 total 37.86
    return all(x in v for x in ["5.00", "2.89", "37.86"])

def p_bad_json(prog):
    r = run(prog, None, raw="{not json")
    return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip() != ""

def p_missing_file(prog):
    r = run(prog, None, path="/nonexistent/dir/inv.json")
    return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip() != ""

def p_type_errors(prog):
    d = {"customer": {"name": "X"}, "items": [{"description": "a", "quantity": True, "unit_price": "5"}], "tax_rate": "8"}
    r = run(prog, d)
    return r.returncode != 0 and "Traceback" not in r.stderr and r.stdout.strip() == "" and len([l for l in r.stderr.splitlines() if l.strip().startswith("-")]) >= 3

def p_toplevel_array(prog):
    r = run(prog, [1, 2])
    return r.returncode != 0 and "Traceback" not in r.stderr

def p_missing_fields(prog):
    r = run(prog, {})
    return r.returncode != 0 and "Traceback" not in r.stderr and all(k in r.stderr for k in ["customer", "items", "tax_rate"])

def p_bad_discount(prog):
    d = dict(BASE); d["discount"] = {"type": "bogus", "value": -3}
    r = run(prog, d)
    return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.count("discount") >= 2

def p_nan(prog):
    r = run(prog, None, raw='{"customer":{"name":"X"},"items":[{"description":"a","quantity":1,"unit_price":NaN}],"tax_rate":0}')
    return r.returncode != 0 and "Traceback" not in r.stderr

def p_discount_exceeds(prog):
    d = dict(BASE); d["discount"] = {"type": "fixed", "value": 1000}
    r = run(prog, d)
    return r.returncode != 0 and "Traceback" not in r.stderr

def p_text_alignment(prog):
    r = run(prog, BASE)
    if r.returncode: return False
    L = r.stdout.rstrip("\n").splitlines()
    item = [l for l in L if l.startswith("Widget")][0]
    tot = [l for l in L if "TOTAL" in l][0]
    return len(item.rstrip()) == len(tot.rstrip())

PROBES = {k: v for k, v in globals().items() if k.startswith("p_")}
res = {}
for side, prog in SIDES.items():
    res[side] = {}
    for name, fn in PROBES.items():
        try: ok = fn(prog)
        except Exception as e: ok = False; print(side, name, "EXC", e)
        res[side][name] = "pass" if ok else "fail"
json.dump(res, open("probes/results.json", "w"), indent=1)
print(json.dumps(res, indent=1))
