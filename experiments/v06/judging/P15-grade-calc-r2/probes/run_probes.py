import json, os, re, subprocess, sys, tempfile, ast

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def w(d, name, text):
    p = os.path.join(d, name)
    open(p, "w").write(text)
    return p

def run(side, args, d):
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, side, "grade_calc.py")] + args,
                       capture_output=True, text=True, cwd=d, timeout=30)
    return r.returncode, r.stdout, r.stderr

SCORES = "student,hw,mid,final\nAlice,95,95,95\nBob,85,85,85\nCara,50,50,50\nDan,100,80,60\n"
# Dan = 100*.3+80*.3+60*.4 = 78
W100 = "assessment,weight\nhw,30\nmid,30\nfinal,40\n"
W10 = "assessment,weight\nhw,3\nmid,3\nfinal,4\n"
WPCT = "assessment,weight\nhw,30%\nmid,30%\nfinal,40%\n"

def row(out, name):
    for l in out.splitlines():
        if l.strip().startswith(name):
            return l
    return ""

def nums(s):
    return [float(x) for x in re.findall(r"-?\d+\.\d+|-?\d+", s)]

def ok_err(rc, out, err):
    return rc != 0 and "Traceback" not in err + out

def probes(side):
    res = {}
    with tempfile.TemporaryDirectory() as d:
        s = w(d, "s.csv", SCORES)
        wa = w(d, "w100.csv", W100); wb = w(d, "w10.csv", W10); wp = w(d, "wp.csv", WPCT)
        rc, out, err = run(side, [s, wa], d)
        res["P01_basic_final"] = "pass" if rc == 0 and 78.0 in nums(row(out, "Dan")) and 95.0 in nums(row(out, "Alice")) else "fail"
        rc2, out2, err2 = run(side, [s, wb], d)
        res["P02_normalize"] = "pass" if rc2 == 0 and 78.0 in nums(row(out2, "Dan")) and 85.0 in nums(row(out2, "Bob")) else "fail"
        a, b, c = row(out, "Alice"), row(out, "Bob"), row(out, "Cara")
        res["P03_letter"] = "pass" if re.search(r"\sA[+-]?\s", a + " ") and re.search(r"\sB[+-]?\s", b + " ") and re.search(r"\sF\s", c + " ") else "fail"
        res["P04_gpa"] = "pass" if 4.0 in nums(a) and 0.0 in nums(c) else "fail"
        stats = out.split("tatistics")[-1].lower() if "tatistics" in out else out.lower()
        def has(label, val):
            for l in stats.splitlines():
                if label in l and any(abs(x - val) < 0.006 for x in nums(l)):
                    return True
            return False
        g = [95, 85, 50, 78]
        import statistics as st
        res["P05_mean"] = "pass" if has("mean", st.mean(g)) else "fail"
        res["P06_median"] = "pass" if has("median", st.median(g)) else "fail"
        res["P07_stdev"] = "pass" if has("std", round(st.pstdev(g), 2)) or has("std", round(st.stdev(g), 2)) else "fail"
        res["P08_high_low"] = "pass" if has("high", 95) and has("low", 50) else "fail"
        rc, out, err = run(side, [s, wp], d)
        res["P09_pct_weights"] = "pass" if rc == 0 and 78.0 in nums(row(out, "Dan")) else "fail"
        res["P10_missing_file"] = "pass" if ok_err(*run(side, [os.path.join(d, "nope.csv"), wa], d)) else "fail"
        bad = w(d, "bad.csv", "student,hw,mid,final\nEve,abc,80,80\n")
        res["P11_nonnumeric_score"] = "pass" if ok_err(*run(side, [bad, wa], d)) else "fail"
        miss = w(d, "miss.csv", "student,hw,mid\nEve,80,80\n")
        res["P12_weight_without_column"] = "pass" if ok_err(*run(side, [miss, wa], d)) else "fail"
        neg = w(d, "neg.csv", "student,hw,mid,final\nEve,-10,80,80\n")
        res["P13_negative_score_rejected"] = "pass" if ok_err(*run(side, [neg, wa], d)) else "fail"
        hdr = w(d, "hdr.csv", "student,hw,mid,final\n")
        res["P14_no_students"] = "pass" if ok_err(*run(side, [hdr, wa], d)) else "fail"
        z = w(d, "z.csv", "assessment,weight\nhw,0\nmid,0\nfinal,0\n")
        res["P15_zero_weights"] = "pass" if ok_err(*run(side, [s, z], d)) else "fail"
        nw = w(d, "nw.csv", "assessment,weight\nhw,abc\nmid,30\nfinal,40\n")
        res["P16_nonnumeric_weight"] = "pass" if ok_err(*run(side, [s, nw], d)) else "fail"
        ragged = w(d, "rg.csv", "student,hw,mid,final\nEve,80,80\n")
        res["P17_ragged_row"] = "pass" if ok_err(*run(side, [ragged, wa], d)) else "fail"
        rc, out, err = run(side, [], d)
        res["P18_usage_no_args"] = "pass" if rc != 0 and "usage" in (out + err).lower() and "Traceback" not in err else "fail"
        one = w(d, "one.csv", "student,hw,mid,final\nSolo,80,80,80\n")
        rc, out, err = run(side, [one, wa], d)
        res["P19_single_student"] = "pass" if rc == 0 and "Traceback" not in err else "fail"
        blank = w(d, "blank.csv", "student,hw,mid,final\nEve,,80,80\nFay,90,90,90\n")
        rc, out, err = run(side, [blank, wa], d)
        res["P20_blank_score_not_silent"] = "pass" if "Traceback" not in err and (rc != 0 or re.search(r"missing|blank|n/?a|zero", err.lower())) else "fail"
    src = open(os.path.join(ROOT, side, "grade_calc.py")).read()
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    res["P21_stdlib_only"] = "pass" if all(m in sys.stdlib_module_names for m in mods) else "fail"
    py = [f for f in os.listdir(os.path.join(ROOT, side)) if f.endswith(".py")]
    res["P22_single_file"] = "pass" if py == ["grade_calc.py"] else "fail"
    return res

out = {"A": probes("A"), "B": probes("B")}
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for k in out["A"]:
    print(k, out["A"][k], out["B"][k])
