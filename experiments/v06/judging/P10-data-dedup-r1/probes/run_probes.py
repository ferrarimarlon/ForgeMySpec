import json, os, subprocess, sys, tempfile, csv, io
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def keyargs(side, cols):
    if side == "A":
        out = []
        for c in cols: out += ["-k", c]
        return out
    return ["-k"] + cols
def run(side, inp_text, cols, strategy, out=True, raw=False):
    d = tempfile.mkdtemp()
    ip = os.path.join(d, "in.csv"); op = os.path.join(d, "out.csv")
    mode = "wb" if raw else "w"
    with open(ip, mode, **({} if raw else {"newline": "", "encoding": "utf-8"})) as f: f.write(inp_text)
    cmd = [sys.executable, "-I", os.path.join(ROOT, side, "data_dedup.py"), ip] + keyargs(side, cols) + ["-s", strategy, "-o", op]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    rows = None
    if os.path.exists(op):
        with open(op, newline="", encoding="utf-8") as f: rows = list(csv.reader(f))
    return p, rows
DATA = "id,name,city\n1,a,X\n2,b,Y\n1,c,Z\n3,d,X\n2,e,Y\n"
COMP = "first,last,age\nJo,Li,1\nJo,Ki,2\nJo,Li,3\nAl,Li,4\n"
def probes(side):
    r = {}
    p, rows = run(side, DATA, ["id"], "first")
    r["P01_first_single"] = p.returncode == 0 and rows == [["id","name","city"],["1","a","X"],["2","b","Y"],["3","d","X"]]
    p, rows = run(side, DATA, ["id"], "last")
    r["P02_last_single"] = p.returncode == 0 and rows is not None and rows[0]==["id","name","city"] and sorted(rows[1:]) == sorted([["1","c","Z"],["3","d","X"],["2","e","Y"]])
    p, rows = run(side, COMP, ["first","last"], "first")
    r["P03_composite_first"] = p.returncode == 0 and rows == [["first","last","age"],["Jo","Li","1"],["Jo","Ki","2"],["Al","Li","4"]]
    p, rows = run(side, COMP, ["first","last"], "last")
    r["P04_composite_last"] = p.returncode == 0 and rows is not None and sorted(rows[1:]) == sorted([["Jo","Ki","2"],["Jo","Li","3"],["Al","Li","4"]])
    p, rows = run(side, DATA, ["id"], "error")
    r["P05_error_nonzero"] = p.returncode != 0
    out = p.stdout + p.stderr
    r["P06_error_reports_dups"] = p.returncode != 0 and "1" in out and "2" in out and "Traceback" not in out and ("dup" in out.lower())
    p, rows = run(side, "id,v\n1,a\n2,b\n", ["id"], "error")
    r["P07_error_nodups_ok"] = p.returncode == 0
    p, rows = run(side, DATA, ["id"], "first")
    import re
    nums = re.findall(r"\d+", p.stdout)
    r["P08_summary_counts"] = p.returncode == 0 and "2" in nums and ("found" in p.stdout.lower() and "removed" in p.stdout.lower())
    p, rows = run(side, DATA, ["nope"], "first")
    r["P09_missing_key_col"] = p.returncode != 0 and "Traceback" not in p.stderr and "nope" in p.stderr
    q = 'id,text\n1,"hello, world"\n1,"multi\nline"\n2,"say ""hi"""\n'
    p, rows = run(side, q, ["id"], "last")
    r["P10_csv_quoting"] = p.returncode == 0 and rows == [["id","text"],["1","multi\nline"],["2",'say "hi"']]
    p, rows = run(side, DATA, ["id","city"], "first")
    r["P11_composite_distinguishes"] = p.returncode == 0 and rows is not None and len(rows) == 5  # (1,X),(2,Y),(1,Z),(3,X) ; (2,Y) dup
    p, rows = run(side, "﻿id,v\n1,a\n1,b\n".encode("utf-8"), ["id"], "first", raw=True)
    r["P12_bom_input"] = p.returncode == 0 and rows is not None and len(rows) == 2
    p, rows = run(side, "", ["id"], "first")
    r["P13_empty_input"] = p.returncode != 0 and "Traceback" not in p.stderr
    p, rows = run(side, DATA, ["id"], "last")
    r["P14_last_preserves_order_of_kept"] = rows == [["id","name","city"],["1","c","Z"],["3","d","X"],["2","e","Y"]]
    return {k: ("pass" if v else "fail") for k, v in r.items()}
res = {s: probes(s) for s in ("A", "B")}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
