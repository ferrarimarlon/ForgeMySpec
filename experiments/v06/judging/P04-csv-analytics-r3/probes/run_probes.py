import ast, json, os, statistics, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def invoke(side, csvpath, filters=(), cols=None, out=None):
    prog = os.path.join(ROOT, side, "csv_analytics.py")
    if side == "A":
        cmd = [sys.executable, prog, csvpath, "-q"]
        for f in filters: cmd += ["-w", f]
        if cols: cmd += ["-c", ",".join(cols)]
        cmd += ["-o", out or "-"]
    else:
        cmd = [sys.executable, prog, csvpath]
        for f in filters: cmd += ["-f", f]
        if cols: cmd += ["-c", *cols]
        if out: cmd += ["-o", out]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

DATA = 'name,age,score,city\nann,30,1.5,NY\nbob,40,2.5,LA\ncy,,3.5,NY\ndee,20,10,SF\n"e, f",50,4,NY\n'
AGES = [30, 40, 20, 50]
STDLIB = {"argparse","csv","json","math","re","statistics","sys","os","io","collections","typing","pathlib","itertools","functools","dataclasses","operator","decimal","fractions","textwrap","string","__future__"}

def run(side):
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "d.csv")
    open(p, "w").write(DATA)
    R = {}
    def rep(*a, **k):
        r = invoke(side, *a, **k)
        try: return json.loads(r.stdout)
        except Exception: return None
    def chk(pid, fn):
        try: R[pid] = "pass" if fn() else "fail"
        except Exception: R[pid] = "fail"
    base = rep(p)
    age = lambda d: d["columns"]["age"]
    chk("P01_reads_csv", lambda: set(base["columns"]) == {"name", "age", "score", "city"})
    chk("P02_count", lambda: age(base)["count"] == 4)
    chk("P03_min", lambda: age(base)["min"] == 20)
    chk("P04_max", lambda: age(base)["max"] == 50)
    chk("P05_mean", lambda: abs(age(base)["mean"] - 35) < 1e-9)
    chk("P06_median", lambda: age(base)["median"] == 35)
    chk("P07_stdev", lambda: abs(age(base)["stdev"] - statistics.stdev(AGES)) < 1e-9)
    chk("P08_filter_numeric", lambda: (lambda d: age(d)["count"] == 2 and age(d)["min"] == 40)(rep(p, ["age>35"])))
    chk("P09_filter_equality_string", lambda: (lambda d: d["columns"]["score"]["count"] == 3)(rep(p, ["city==NY"])))
    chk("P10_filter_and", lambda: (lambda d: d["columns"]["score"]["count"] == 2)(rep(p, ["city==NY", "age>=30"])))
    chk("P11_select_columns", lambda: list(rep(p, cols=["score", "age"])["columns"]) in (["score", "age"], ["age", "score"]))
    def p12():
        o = os.path.join(tmp, "out.json")
        r = invoke(side, p, out=o)
        d = json.load(open(o))
        return r.returncode == 0 and d["columns"]["age"]["max"] == 50
    chk("P12_json_export_file", p12)
    def p13():
        files = [f for f in os.listdir(os.path.join(ROOT, side)) if f.endswith(".py")]
        tree = ast.parse(open(os.path.join(ROOT, side, "csv_analytics.py")).read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            if isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
        return files == ["csv_analytics.py"] and mods <= STDLIB
    chk("P13_single_file_stdlib", p13)
    chk("P14_quoted_field", lambda: base["columns"]["name"]["count"] == 5)
    chk("P15_text_column_no_numeric_stats", lambda: base["columns"]["name"]["mean"] is None)
    def err_ok(r): return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip() != ""
    chk("P16_missing_file_error", lambda: err_ok(invoke(side, os.path.join(tmp, "nope.csv"))))
    chk("P17_unknown_select_column", lambda: err_ok(invoke(side, p, cols=["zzz"])))
    chk("P18_unknown_filter_column", lambda: err_ok(invoke(side, p, ["zzz>1"])))
    chk("P19_malformed_filter", lambda: err_ok(invoke(side, p, ["age"])))
    bad = os.path.join(tmp, "latin.csv"); open(bad, "wb").write(b"n,v\n\xe9t\xe9,1\n")
    chk("P20_non_utf8_no_traceback", lambda: (lambda r: r.returncode == 0 or err_ok(r))(invoke(side, bad)))
    empty = os.path.join(tmp, "empty.csv"); open(empty, "w").write("")
    chk("P21_empty_file_error", lambda: err_ok(invoke(side, empty)))
    hdr = os.path.join(tmp, "hdr.csv"); open(hdr, "w").write("a,b\n")
    chk("P22_header_only", lambda: (lambda d: d["columns"]["a"]["count"] == 0)(rep(hdr)))
    chk("P23_filter_no_match", lambda: (lambda d: age(d)["count"] == 0 and age(d)["mean"] is None)(rep(p, ["age>1000"])))
    single = rep(p, ["age==20"])
    chk("P24_single_value_stdev_null", lambda: age(single)["count"] == 1 and age(single)["stdev"] is None)
    dup = os.path.join(tmp, "dup.csv"); open(dup, "w").write("v,v\n1,2\n")
    chk("P25_duplicate_header_not_silent", lambda: (lambda r: r.returncode != 0 or len(json.loads(r.stdout)["columns"]) == 2)(invoke(side, dup)))
    mix = os.path.join(tmp, "mix.csv"); open(mix, "w").write("v\n1\n2\nN/A\n10\n")
    chk("P26_mixed_column_numeric_stats", lambda: (lambda d: d["columns"]["v"]["max"] == 10 and d["columns"]["v"]["mean"] is not None)(rep(mix)))
    return R

res = {"A": run("A"), "B": run("B")}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for k in res["A"]: print(k, res["A"][k], res["B"][k])
