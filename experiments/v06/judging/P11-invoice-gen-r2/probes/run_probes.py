import json, subprocess, sys, tempfile, os, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = {"customer": {"name": "Acme", "email": "a@b.co"},
        "items": [{"description": "Widget", "quantity": 3, "unit_price": 9.99},
                  {"description": "Gadget", "quantity": 2, "unit_price": 1.005}],
        "tax_rate": 8.5, "discount": {"type": "percent", "value": 10}}

def run(side, data, fmt=None, raw=None, path=None, extra=()):
    d = tempfile.mkdtemp()
    p = path or os.path.join(d, "inv.json")
    if path is None:
        with open(p, "w") as f:
            f.write(raw if raw is not None else json.dumps(data))
    cmd = [sys.executable, "-I", os.path.join(ROOT, side, "invoice_gen.py"), p]
    if fmt: cmd += ["--format", fmt]
    cmd += list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, cwd=d)
    return r, d

def jout(side, data):
    r, _ = run(side, data, "json")
    return r.returncode, json.loads(r.stdout) if r.returncode == 0 else None

def num(v): 
    from decimal import Decimal; return Decimal(str(v))

def p_valid_text(s):
    r,_ = run(s, BASE); return r.returncode == 0 and "Widget" in r.stdout and "Acme" in r.stdout
def p_json_valid(s):
    rc, j = jout(s, BASE); return rc == 0 and isinstance(j, dict)
# lines: 29.97 ; 2*1.005=2.01 ; sub 31.98 ; disc 3.198->3.20 ; taxable 28.78 ; tax 2.4463->2.45 ; total 31.23
def p_line_totals(s):
    rc, j = jout(s, BASE); return rc==0 and [num(i["line_total"]) for i in j["items"]] == [num("29.97"), num("2.01")]
def p_subtotal(s):
    rc, j = jout(s, BASE); return rc==0 and num(j["subtotal"]) == num("31.98")
def p_discount(s):
    rc, j = jout(s, BASE); return rc==0 and num(j["discount"]) == num("3.20")
def p_tax(s):
    rc, j = jout(s, BASE); return rc==0 and num(j["tax"]) == num("2.45")
def p_total(s):
    rc, j = jout(s, BASE); return rc==0 and num(j["total"]) == num("31.23")
def p_text_totals(s):
    r,_ = run(s, BASE); return r.returncode==0 and all(x in r.stdout for x in ["29.97","2.01","31.98","3.20","2.45","31.23"])
def p_round_half_up(s):
    d = {"customer":{"name":"X"},"items":[{"description":"a","quantity":1,"unit_price":0.125}],"tax_rate":0}
    rc, j = jout(s, d); return rc==0 and num(j["total"]) == num("0.13")
def p_float_sum(s):
    d = {"customer":{"name":"X"},"items":[{"description":"a","quantity":1,"unit_price":0.1},{"description":"b","quantity":1,"unit_price":0.2}],"tax_rate":0}
    rc, j = jout(s, d); return rc==0 and j["total"] == "0.30"
def p_two_decimals(s):
    rc, j = jout(s, BASE); return rc==0 and all(len(str(j[k]).split(".")[-1])==2 for k in ("subtotal","tax","total"))
def p_no_discount(s):
    d = dict(BASE); d.pop("discount")
    rc, j = jout(s, d); return rc==0 and num(j["discount"]) == 0 and num(j["total"]) == num("34.70")
def p_fixed_discount(s):
    d = dict(BASE); d["discount"] = {"type":"fixed","value":5}
    # taxable 26.98 tax 2.2933->2.29 total 29.27
    rc, j = jout(s, d); return rc==0 and num(j["total"]) == num("29.27")
def p_all_errors(s):
    d = {"customer":{},"items":[{"description":"","quantity":-1,"unit_price":"x"}],"tax_rate":-5}
    r,_ = run(s, d); e = r.stderr
    return r.returncode != 0 and all(k in e for k in ["customer.name","description","quantity","unit_price","tax_rate"]) and "Traceback" not in e
def p_errors_two_items(s):
    d = {"customer":{"name":"X"},"items":[{"description":"a","quantity":0,"unit_price":1},{"description":"b","quantity":1,"unit_price":-1}],"tax_rate":0}
    r,_ = run(s, d); return r.returncode != 0 and "items[0]" in r.stderr and "items[1]" in r.stderr
def p_missing_customer(s):
    d = dict(BASE); d.pop("customer"); r,_ = run(s, d); return r.returncode != 0 and "customer" in r.stderr and "Traceback" not in r.stderr
def p_missing_items(s):
    d = dict(BASE); d.pop("items"); r,_ = run(s, d); return r.returncode != 0 and "items" in r.stderr and "Traceback" not in r.stderr
def p_bool_qty(s):
    d = json.loads(json.dumps(BASE)); d["items"][0]["quantity"] = True
    r,_ = run(s, d); return r.returncode != 0 and "quantity" in r.stderr
def p_bad_json(s):
    r,_ = run(s, None, raw="{not json"); return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip()
def p_missing_file(s):
    r,_ = run(s, None, path="/nonexistent/x.json"); return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip()
def p_nan(s):
    r,_ = run(s, None, raw='{"customer":{"name":"X"},"items":[{"description":"a","quantity":1,"unit_price":NaN}],"tax_rate":0}')
    return r.returncode != 0 and "Traceback" not in r.stderr
def p_top_array(s):
    r,_ = run(s, [1,2]); return r.returncode != 0 and "Traceback" not in r.stderr
def p_discount_exceeds(s):
    d = dict(BASE); d["discount"] = {"type":"fixed","value":1000}
    r,_ = run(s, d); return r.returncode != 0 and "discount" in r.stderr and "Traceback" not in r.stderr
def p_bad_discount_type(s):
    d = dict(BASE); d["discount"] = {"type":"bogus","value":5}
    r,_ = run(s, d); return r.returncode != 0 and "discount" in r.stderr
def p_huge_number(s):
    d = {"customer":{"name":"X"},"items":[{"description":"a","quantity":1,"unit_price":1e30}],"tax_rate":0}
    r,_ = run(s, d); return "Traceback" not in r.stderr
def p_customer_extra_float_json(s):
    d = json.loads(json.dumps(BASE)); d["customer"]["credit"] = 1.5
    r,_ = run(s, d, "json"); return r.returncode == 0 and "Traceback" not in r.stderr
def p_output_file(s):
    r, d = run(s, BASE, "json", extra=("--output", "out.json"))
    f = os.path.join(d, "out.json")
    return r.returncode == 0 and os.path.exists(f) and json.load(open(f))["total"] in ("31.23", 31.23)
def p_stdlib_only(s):
    tree = ast.parse(open(os.path.join(ROOT, s, "invoice_gen.py")).read())
    std = {"argparse","json","sys","decimal","datetime","os","re","math","typing","pathlib","io","string","textwrap","collections","itertools","functools"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            if any(a.name.split(".")[0] not in std for a in n.names): return False
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] not in std: return False
    return True

PROBES = {k: v for k, v in globals().items() if k.startswith("p_")}
res = {}
for side in ("A", "B"):
    res[side] = {}
    for name, fn in PROBES.items():
        try: ok = bool(fn(side))
        except Exception as e: ok = False; print(side, name, "EXC", e)
        res[side][name[2:]] = "pass" if ok else "fail"
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for side in res:
    print(side, sum(v=="pass" for v in res[side].values()), "/", len(res[side]), [k for k,v in res[side].items() if v=="fail"])
