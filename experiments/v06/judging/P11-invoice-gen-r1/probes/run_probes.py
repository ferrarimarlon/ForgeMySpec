import json, os, subprocess, sys, tempfile, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = {"customer":{"name":"Acme"},"items":[{"description":"Widget","quantity":3,"unit_price":0.335},
        {"description":"Gadget","quantity":1,"unit_price":10}],"tax_rate":8.25}
def run(side, args, stdin=None):
    p = os.path.join(ROOT, side, "invoice_gen.py")
    if not os.path.exists(p): return None
    return subprocess.run([sys.executable, "-I", p]+args, capture_output=True, text=True, input=stdin, timeout=20)
def wf(d, obj, raw=None):
    f = os.path.join(d, "in.json"); open(f,"w").write(raw if raw is not None else json.dumps(obj)); return f
def jout(side, d, obj):
    r = run(side, [wf(d,obj), "--format","json"]); 
    return json.loads(r.stdout) if r and r.returncode==0 else None
def probes(side, d):
    res = {}
    p = os.path.join(ROOT, side, "invoice_gen.py")
    res["P01_single_file_exists"] = os.path.exists(p) and [f for f in os.listdir(os.path.join(ROOT,side)) if f.endswith(".py")]==["invoice_gen.py"]
    if os.path.exists(p):
        mods=set()
        for n in ast.walk(ast.parse(open(p).read())):
            if isinstance(n, ast.Import): mods|={a.name.split(".")[0] for a in n.names}
            if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
        res["P02_stdlib_only"] = all(m in getattr(sys,"stdlib_module_names",{"argparse","datetime","json","sys","decimal","os","re","math","typing","pathlib","io","dataclasses","collections","textwrap","enum","__future__"}) for m in mods)
    else: res["P02_stdlib_only"]=False
    r = run(side, [wf(d,BASE)])
    res["P03_text_output"] = bool(r and r.returncode==0 and "Widget" in r.stdout and "Acme" in r.stdout)
    # 3*0.335=1.005 -> 1.01 ; subtotal 11.01 ; tax 8.25% = 0.908325 -> 0.91 ; total 11.92
    res["P04_text_totals"] = bool(r and r.returncode==0 and all(x in r.stdout for x in ["1.01","11.01","0.91","11.92"]))
    j = jout(side, d, BASE)
    def num(v):
        try: return f"{float(v):.2f}"
        except Exception: return None
    flat = json.dumps(j) if j else ""
    res["P05_json_export_valid"] = j is not None
    res["P06_json_line_total_halfup"] = bool(j and "1.01" in flat and "1.00\"" not in flat)
    res["P07_json_grand_total"] = bool(j and ("11.92" in flat))
    b = dict(BASE, discount={"type":"percent","value":10})
    # subtotal 11.01, discount 1.101->1.10, taxable 9.91, tax .817575->0.82, total 10.73
    j = jout(side, d, b); flat=json.dumps(j) if j else ""
    res["P08_percent_discount"] = bool(j and "1.10" in flat and "10.73" in flat)
    b = dict(BASE, discount={"type":"fixed","value":2})
    # taxable 9.01 tax 0.743325->0.74 total 9.75
    j = jout(side, d, b); flat=json.dumps(j) if j else ""
    res["P09_fixed_discount"] = bool(j and "9.75" in flat)
    b = {"customer":{"name":"X"},"items":[{"description":"a","quantity":3,"unit_price":0.1}],"tax_rate":0}
    j = jout(side, d, b); flat=json.dumps(j) if j else ""
    res["P10_no_float_artifacts"] = bool(j and "0.30" in flat and "0.30000000000000004" not in flat)
    bad = {"customer":{},"items":[{"description":"","quantity":-1,"unit_price":"x"}],"tax_rate":-5}
    r = run(side, [wf(d,bad)])
    out = (r.stdout+r.stderr) if r else ""
    res["P11_invalid_nonzero_exit"] = bool(r and r.returncode!=0 and "TOTAL" not in r.stdout)
    res["P12_all_errors_reported"] = bool(r and sum(k in out for k in ["name","description","quantity","unit_price","tax"])>=5)
    r = run(side, [wf(d,None,raw="{not json")])
    res["P13_malformed_json_clean"] = bool(r and r.returncode!=0 and "Traceback" not in r.stderr)
    r = run(side, [os.path.join(d,"nope.json")])
    res["P14_missing_file_clean"] = bool(r and r.returncode!=0 and "Traceback" not in r.stderr)
    r = run(side, [wf(d,{"customer":{"name":"A"},"items":[]})])
    res["P15_missing_tax_and_empty_items"] = bool(r and r.returncode!=0 and "Traceback" not in r.stderr and "tax" in r.stderr.lower())
    r = run(side, [wf(d,dict(BASE, items=[{"description":"a","quantity":True,"unit_price":1}]))])
    res["P16_bool_quantity_rejected"] = bool(r and r.returncode!=0 and "Traceback" not in r.stderr)
    r = run(side, [wf(d,dict(BASE, discount={"type":"percent","value":150}))])
    res["P17_bad_discount_rejected"] = bool(r and r.returncode!=0 and "Traceback" not in r.stderr)
    r = run(side, [wf(d,None,raw='{"customer":{"name":"A"},"items":[{"description":"a","quantity":1,"unit_price":1e40}],"tax_rate":5}')])
    res["P18_huge_number_no_traceback"] = bool(r and "Traceback" not in r.stderr)
    r = run(side, [wf(d,None,raw='{"customer":{"name":"A"},"items":[{"description":"a","quantity":1,"unit_price":NaN}],"tax_rate":5}')])
    res["P19_nan_rejected"] = bool(r and r.returncode!=0 and "Traceback" not in r.stderr)
    j = jout(side, d, dict(BASE, customer={"name":"A","id":42}))
    res["P20_json_export_numeric_customer_field"] = j is not None
    return {k:("pass" if v else "fail") for k,v in res.items()}
out={}
for s in ("A","B"):
    with tempfile.TemporaryDirectory() as d: out[s]=probes(s,d)
json.dump(out, open(os.path.join(ROOT,"probes","results.json"),"w"), indent=1)
print(json.dumps(out, indent=1))
