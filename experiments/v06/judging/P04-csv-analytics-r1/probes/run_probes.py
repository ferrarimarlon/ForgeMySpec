import ast, json, math, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STDLIB = set(sys.stdlib_module_names)

def run(side, csvpath, filters=(), cols=None, out=None):
    prog = os.path.join(ROOT, side, "csv_analytics.py")
    cmd = [sys.executable, "-I", prog, csvpath]
    for f in filters:
        cmd += (["-w", f] if side == "A" else ["--filter", f])
    if cols is not None:
        cmd += (["-c", cols] if side == "A" else ["--columns", cols])
    if out:
        cmd += (["-o", out] if side == "A" else ["--output", out])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

def report(side, tmp, text, filters=(), cols=None):
    p = os.path.join(tmp, "in.csv"); open(p, "w").write(text)
    o = os.path.join(tmp, "out.json")
    if os.path.exists(o): os.remove(o)
    r = run(side, p, filters, cols, o)
    if r.returncode != 0: raise AssertionError(r.stderr)
    return json.load(open(o))

def nrows(side, rep): return rep["matched_rows"] if side == "A" else rep["rows"]
def close(a, b): return a is not None and math.isclose(a, b, rel_tol=1e-6)

NUM = "id,age,city\n1,25,Paris\n2,35,Rome\n3,45,Paris\n4,30,Oslo\n5,40,Rome\n"

def p_single_file(side, tmp):
    return os.path.isfile(os.path.join(ROOT, side, "csv_analytics.py"))
def p_stdlib(side, tmp):
    t = ast.parse(open(os.path.join(ROOT, side, "csv_analytics.py")).read())
    mods = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    return mods <= STDLIB
def p_stats_odd(side, tmp):
    s = report(side, tmp, NUM)["columns"]["age"]
    return (s["count"] == 5 and s["min"] == 25 and s["max"] == 45 and close(s["mean"], 35)
            and close(s["median"], 35) and close(s["stdev"], 7.9056941504))
def p_median_even(side, tmp):
    s = report(side, tmp, "x\n1\n2\n3\n4\n")["columns"]["x"]
    return close(s["median"], 2.5) and close(s["mean"], 2.5) and close(s["stdev"], 1.2909944487)
def p_filter_numeric(side, tmp):
    r = report(side, tmp, NUM, filters=["age>30"])
    return nrows(side, r) == 3 and r["columns"]["age"]["min"] == 35
def p_filter_numeric_not_lexical(side, tmp):
    r = report(side, tmp, "v\n9\n10\n100\n", filters=["v>=10"])
    return nrows(side, r) == 2
def p_filter_string_eq(side, tmp):
    r = report(side, tmp, NUM, filters=["city==Paris"])
    return nrows(side, r) == 2 and close(r["columns"]["age"]["mean"], 35)
def p_filter_and(side, tmp):
    r = report(side, tmp, NUM, filters=["city==Rome", "age<40"])
    return nrows(side, r) == 1
def p_select(side, tmp):
    r = report(side, tmp, NUM, cols="age,id")
    return set(r["columns"]) == {"age", "id"}
def p_json_valid(side, tmp):
    r = report(side, tmp, NUM)
    return isinstance(r, dict) and all(k in r["columns"]["age"] for k in
                                       ["count", "min", "max", "mean", "median", "stdev"])
def p_quoted(side, tmp):
    r = report(side, tmp, 'name,val\n"Smith, J",10\n"Doe, ""A""",20\n')
    return r["columns"]["name"]["count"] == 2 and close(r["columns"]["val"]["mean"], 15)
def p_missing_values(side, tmp):
    s = report(side, tmp, "a,b\n1,x\n,y\n3,z\n")["columns"]["a"]
    return s["count"] == 2 and close(s["mean"], 2)
def p_text_column(side, tmp):
    s = report(side, tmp, NUM)["columns"]["city"]
    return s["count"] == 5
def p_mixed_column_no_crash(side, tmp):
    s = report(side, tmp, "a\n1\nN/A\n3\n")["columns"]["a"]
    return s["count"] == 3
def p_single_value(side, tmp):
    s = report(side, tmp, "a\n7\n")["columns"]["a"]
    return s["count"] == 1 and close(s["mean"], 7)
def p_ragged(side, tmp):
    r = report(side, tmp, "a,b\n1,2\n3\n4,5,6\n")
    return r["columns"]["a"]["count"] == 3
def _err(r): return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip() != ""
def p_err_missing_file(side, tmp):
    return _err(run(side, os.path.join(tmp, "nope.csv")))
def p_err_unknown_select(side, tmp):
    p = os.path.join(tmp, "in.csv"); open(p, "w").write(NUM)
    return _err(run(side, p, cols="zzz"))
def p_err_unknown_filter(side, tmp):
    p = os.path.join(tmp, "in.csv"); open(p, "w").write(NUM)
    return _err(run(side, p, filters=["zzz>1"]))
def p_err_bad_filter(side, tmp):
    p = os.path.join(tmp, "in.csv"); open(p, "w").write(NUM)
    return _err(run(side, p, filters=["age"]))
def p_err_empty_file(side, tmp):
    p = os.path.join(tmp, "in.csv"); open(p, "w").write("")
    return _err(run(side, p))

PROBES = {k[2:]: v for k, v in globals().items() if k.startswith("p_")}
if __name__ == "__main__":
    res, details = {}, {}
    for side in ("A", "B"):
        res[side] = {}
        for pid, fn in PROBES.items():
            with tempfile.TemporaryDirectory() as tmp:
                try: ok = bool(fn(side, tmp)); err = ""
                except Exception as e: ok = False; err = repr(e)[:200]
            res[side][pid] = "pass" if ok else "fail"
            if not ok: details[f"{side}:{pid}"] = err
    json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
    print(json.dumps(res, indent=1)); print(details)
