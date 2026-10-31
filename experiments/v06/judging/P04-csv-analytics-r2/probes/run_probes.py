"""Black-box probes. Only the invocation adapter differs per side."""
import json, os, subprocess, sys, tempfile, statistics, ast

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def adapter(side):
    if side == "A":
        return {"select": "--select", "filter": "--filter", "out": "--output"}
    return {"select": "-c", "filter": "-w", "out": "-o"}

def run(side, csvpath, select=None, filters=(), tmp=None):
    ad = adapter(side)
    out = os.path.join(tmp, "report.json")
    if os.path.exists(out):
        os.remove(out)
    cmd = [sys.executable, os.path.join(ROOT, side, "csv_analytics.py"), csvpath, ad["out"], out]
    if select:
        cmd += [ad["select"], select]
    for f in filters:
        cmd += [ad["filter"], f]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp, timeout=30)
    rep = None
    if os.path.exists(out):
        try:
            rep = json.load(open(out))
        except Exception:
            rep = "INVALID"
    return p, rep

def stats(side, rep):
    if not isinstance(rep, dict):
        return None
    if side == "A":
        return rep.get("stats")
    return next(iter(rep.values())).get("stats")

def matched(side, rep):
    if side == "A":
        return rep.get("row_count")
    return next(iter(rep.values())).get("rows_matched")

def write(tmp, name, data, mode="w"):
    p = os.path.join(tmp, name)
    with open(p, mode) as f:
        f.write(data)
    return p

SAMPLE = "name,age,city,score\nann,30,rio,1.5\nbob,25,sao,2.5\ncid,35,rio,3.5\ndee,,sao,4.5\neve,40,\"rio, br\",5.5\n"

def clean_err(p):
    return p.returncode != 0 and "Traceback" not in p.stderr and p.stderr.strip() != ""

def probes(side):
    r = {}
    tmp = tempfile.mkdtemp()
    s = write(tmp, "s.csv", SAMPLE)
    p, rep = run(side, s, tmp=tmp)
    st = stats(side, rep) or {}
    sc = st.get("score", {})
    vals = [1.5, 2.5, 3.5, 4.5, 5.5]
    r["P01_count_min_max"] = sc.get("count") == 5 and sc.get("min") == 1.5 and sc.get("max") == 5.5
    r["P02_mean"] = sc.get("mean") == 3.5
    r["P03_median_odd"] = sc.get("median") == 3.5
    r["P04_stdev_sample"] = sc.get("stdev") is not None and abs(sc["stdev"] - statistics.stdev(vals)) < 1e-9
    ag = st.get("age", {})
    r["P05_median_even_and_blank_skip"] = ag.get("count") == 4 and ag.get("median") == 32.5
    r["P06_json_export_valid"] = p.returncode == 0 and isinstance(rep, dict) and set(st) == {"name", "age", "city", "score"}
    nm = st.get("name", {})
    r["P07_text_column_count"] = nm.get("count") == 5 and nm.get("mean") is None
    # quoted field with comma
    r["P08_quoted_field"] = st.get("city", {}).get("count") == 5
    # filters
    p, rep = run(side, s, filters=["age>28"], tmp=tmp)
    r["P09_filter_numeric_gt"] = p.returncode == 0 and matched(side, rep) == 3 and stats(side, rep)["age"]["min"] == 30
    p, rep = run(side, s, filters=["city==rio"], tmp=tmp)
    r["P10_filter_string_eq"] = p.returncode == 0 and matched(side, rep) == 2
    p, rep = run(side, s, filters=["city==rio", "age>30"], tmp=tmp)
    r["P11_filters_anded"] = p.returncode == 0 and matched(side, rep) == 1
    p, rep = run(side, s, filters=["age>1000"], tmp=tmp)
    r["P12_filter_zero_rows"] = p.returncode == 0 and matched(side, rep) == 0 and stats(side, rep)["age"]["mean"] is None
    # select
    p, rep = run(side, s, select="age,score", tmp=tmp)
    r["P13_select_columns"] = p.returncode == 0 and set(stats(side, rep) or {}) == {"age", "score"}
    p, rep = run(side, s, select="age", filters=["city==sao"], tmp=tmp)
    r["P14_select_plus_filter"] = p.returncode == 0 and set(stats(side, rep)) == {"age"} and stats(side, rep)["age"]["count"] == 1
    # errors
    p, _ = run(side, os.path.join(tmp, "nope.csv"), tmp=tmp)
    r["P15_missing_file_clean_error"] = clean_err(p)
    p, _ = run(side, s, select="bogus", tmp=tmp)
    r["P16_unknown_select_clean_error"] = clean_err(p)
    p, _ = run(side, s, filters=["bogus>1"], tmp=tmp)
    r["P17_unknown_filter_col_clean_error"] = clean_err(p)
    p, _ = run(side, s, filters=["no operator here"], tmp=tmp)
    r["P18_malformed_filter_clean_error"] = clean_err(p)
    e = write(tmp, "e.csv", "")
    p, _ = run(side, e, tmp=tmp)
    r["P19_empty_file_clean_error"] = clean_err(p)
    b = write(tmp, "b.csv", b"name,v\n\xff\xfe,1\n", "wb")
    p, _ = run(side, b, tmp=tmp)
    r["P20_non_utf8_clean_error"] = clean_err(p)
    # BOM header
    bom = write(tmp, "bom.csv", "﻿id,v\n1,2\n3,4\n", "w")
    p, rep = run(side, bom, tmp=tmp)
    r["P21_bom_header"] = p.returncode == 0 and "id" in (stats(side, rep) or {})
    # mixed numeric column with N/A placeholder
    m = write(tmp, "m.csv", "v\n1\n2\nN/A\n3\n")
    p, rep = run(side, m, tmp=tmp)
    mv = (stats(side, rep) or {}).get("v", {})
    r["P22_numeric_stats_with_NA_cell"] = mv.get("mean") == 2.0 and mv.get("median") == 2.0
    # numeric filter on numeric column compares numerically (10 > 9)
    n = write(tmp, "n.csv", "v\n9\n10\n100\n")
    p, rep = run(side, n, filters=["v>9"], tmp=tmp)
    r["P23_numeric_not_lexical_filter"] = p.returncode == 0 and matched(side, rep) == 2
    # single file + stdlib
    src = open(os.path.join(ROOT, side, "csv_analytics.py")).read()
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    r["P24_stdlib_only"] = mods <= {"argparse","csv","json","math","operator","re","statistics","sys","os","io","collections","itertools","pathlib","typing","dataclasses","functools"}
    return {k: "pass" if v else "fail" for k, v in r.items()}

if __name__ == "__main__":
    res = {"A": probes("A"), "B": probes("B")}
    json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=2)
    for k in res["A"]:
        print(f"{k:40s} A={res['A'][k]:5s} B={res['B'][k]}")
