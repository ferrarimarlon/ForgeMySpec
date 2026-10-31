import csv, json, os, subprocess, sys, tempfile, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def keyargs(side, keys):
    return ["-k", ",".join(keys)] if side == "A" else ["-k", *keys]

def run(side, content, keys, strategy=None, raw=False, inname="in.csv", create=True):
    d = tempfile.mkdtemp()
    inp = os.path.join(d, inname); out = os.path.join(d, "out.csv")
    if create:
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(inp, mode, **({} if mode == "wb" else {"newline": ""})) as f: f.write(content)
    cmd = [sys.executable, "-I", os.path.join(ROOT, side, "data_dedup.py"), inp, out] + keyargs(side, keys)
    if strategy: cmd += ["-s", strategy]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=d, timeout=30)
    rows = None
    if os.path.exists(out):
        with open(out, newline="", encoding="utf-8") as f: rows = list(csv.reader(f))
    return p, rows

BASIC = "id,name,v\n1,a,x\n2,b,y\n1,c,z\n3,d,w\n2,e,q\n"
COMP = "a,b,v\n1,x,p\n1,y,q\n1,x,r\n2,x,s\n"

def P(side):
    r = {}
    p, rows = run(side, BASIC, ["id"], "first")
    r["P01_first_single"] = p.returncode == 0 and rows == [["id","name","v"],["1","a","x"],["2","b","y"],["3","d","w"]]
    p, rows = run(side, BASIC, ["id"], "last")
    r["P02_last_single"] = p.returncode == 0 and rows is not None and rows[0]==["id","name","v"] and sorted(rows[1:]) == sorted([["1","c","z"],["3","d","w"],["2","e","q"]])
    p, rows = run(side, COMP, ["a","b"], "first")
    r["P03_composite_first"] = p.returncode == 0 and rows == [["a","b","v"],["1","x","p"],["1","y","q"],["2","x","s"]]
    p, rows = run(side, COMP, ["a","b"], "last")
    r["P04_composite_last"] = p.returncode == 0 and rows is not None and sorted(rows[1:]) == sorted([["1","y","q"],["1","x","r"],["2","x","s"]])
    p, rows = run(side, BASIC, ["id"], "error")
    r["P05_error_nonzero"] = p.returncode != 0
    r["P06_error_reports_dups"] = p.returncode != 0 and "1" in (p.stdout+p.stderr) and "2" in (p.stdout+p.stderr) and re.search(r"dup", (p.stdout+p.stderr), re.I) is not None
    p, rows = run(side, "id,v\n1,a\n2,b\n", ["id"], "error")
    r["P07_error_no_dups_ok"] = p.returncode == 0 and rows == [["id","v"],["1","a"],["2","b"]]
    p, rows = run(side, BASIC, ["id"], "first")
    o = p.stdout + p.stderr
    r["P08_summary_counts"] = "2" in o and re.search(r"found", o, re.I) is not None and re.search(r"removed", o, re.I) is not None
    p, rows = run(side, BASIC, ["nope"], "first")
    r["P09_unknown_key"] = p.returncode != 0 and "Traceback" not in p.stderr
    q = 'id,txt\n1,"a, b"\n1,"x"\n2,"line1\nline2"\n'
    p, rows = run(side, q, ["id"], "first")
    r["P10_quoting"] = p.returncode == 0 and rows == [["id","txt"],["1","a, b"],["2","line1\nline2"]]
    p, rows = run(side, "", ["id"], "first", create=False)
    r["P11_missing_input"] = p.returncode != 0 and "Traceback" not in p.stderr
    p, rows = run(side, "id,v\n", ["id"], "first")
    r["P12_header_only"] = p.returncode == 0 and rows == [["id","v"]]
    p, rows = run(side, BASIC, ["id"])
    r["P13_default_strategy_runs"] = p.returncode == 0 and rows is not None and len(rows) == 4
    p, rows = run(side, "﻿id,v\n1,a\n1,b\n".encode("utf-8"), ["id"], "first")
    r["P14_bom_header"] = p.returncode == 0 and rows is not None and len(rows) == 2
    p, rows = run(side, "id,v\n1,a\n\n1,b\n2,c\n", ["id"], "first")
    r["P15_blank_line"] = p.returncode == 0 and rows is not None and rows[1:] == [["1","a"],["2","c"]]
    p, rows = run(side, b"id,v\n1,\xff\n", ["id"], "first")
    r["P16_bad_encoding_no_traceback"] = "Traceback" not in p.stderr and p.returncode != 0
    p, rows = run(side, "id,v\n1,a\n1,b\n", ["id"], "error")
    r["P17_error_no_output_or_unchanged"] = p.returncode != 0 and (rows is None or rows == [["id","v"],["1","a"],["1","b"]])
    return {k: ("pass" if v else "fail") for k, v in r.items()}

res = {"A": P("A"), "B": P("B")}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
