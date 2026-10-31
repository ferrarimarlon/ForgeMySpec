import json, os, re, subprocess, sys, tempfile, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def invoke(side, scores, weights):
    prog = os.path.join(ROOT, side, "grade_calc.py")
    if side == "A":
        cmd = [sys.executable, prog, scores, "-w", weights]
    else:
        cmd = [sys.executable, prog, scores, weights]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

def write(d, name, content, binary=False):
    p = os.path.join(d, name)
    with open(p, "wb" if binary else "w") as f:
        f.write(content)
    return p

SC = "student,hw,mid,final\nAnn,90,80,70\nBob,100,100,100\nCy,50,40,30\n"
W100 = "assessment,weight\nhw,20\nmid,30\nfinal,50\n"
W10 = "assessment,weight\nhw,2\nmid,3\nfinal,5\n"
# grades: Ann 77, Bob 100, Cy 10+12+15=37
G = [77.0, 100.0, 37.0]

def line_for(out, name):
    for l in out.splitlines():
        if re.match(rf"\s*{name}\b", l):
            return l
    return ""

def nums(s):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]

def clean_err(r):
    return r.returncode != 0 and "Traceback" not in r.stderr and r.stderr.strip() != ""

def probes(side):
    res = {}
    with tempfile.TemporaryDirectory() as d:
        s = write(d, "s.csv", SC); w = write(d, "w.csv", W100); w10 = write(d, "w10.csv", W10)
        r = invoke(side, s, w)
        res["P01_runs_ok"] = r.returncode == 0 and "Traceback" not in r.stderr
        src = open(os.path.join(ROOT, side, "grade_calc.py")).read()
        imps = set(re.findall(r"^\s*(?:import|from)\s+(\w+)", src, re.M))
        res["P02_stdlib_only"] = all(m in sys.stdlib_module_names for m in imps)
        res["P03_final_grade"] = "77.00" in line_for(r.stdout, "Ann") and "37.00" in line_for(r.stdout, "Cy")
        r10 = invoke(side, s, w10)
        res["P04_normalize"] = r10.returncode == 0 and "77.00" in line_for(r10.stdout, "Ann") and "37.00" in line_for(r10.stdout, "Cy")
        bob = line_for(r.stdout, "Bob"); cy = line_for(r.stdout, "Cy")
        res["P05_letter"] = bool(re.search(r"\bA[+-]?\b", bob)) and bool(re.search(r"\bF\b", cy))
        res["P06_gpa"] = "4.0" in bob.split("100.00", 1)[-1] and "0.0" in cy.split("37.00", 1)[-1]
        out = r.stdout.lower()
        mean = f"{statistics.fmean(G):.2f}"; med = f"{statistics.median(G):.2f}"
        sd = {f"{statistics.stdev(G):.2f}", f"{statistics.pstdev(G):.2f}"}
        def stat(label, vals):
            for l in out.splitlines():
                if label in l and any(v in l for v in vals):
                    return True
            return False
        res["P07_mean"] = stat("mean", [mean])
        res["P08_median"] = stat("median", [med])
        res["P09_stdev"] = stat("std", sd)
        res["P10_highest"] = stat("high", ["100.00"])
        res["P11_lowest"] = stat("low", ["37.00"])
        res["P12_missing_file"] = clean_err(invoke(side, os.path.join(d, "nope.csv"), w))
        res["P13_bad_score"] = clean_err(invoke(side, write(d, "b.csv", "student,hw,mid,final\nAnn,abc,80,70\n"), w))
        res["P14_unknown_weight_assessment"] = clean_err(invoke(side, s, write(d, "wx.csv", "assessment,weight\nhw,20\nmid,30\nquiz,50\n")))
        res["P15_negative_weight"] = clean_err(invoke(side, s, write(d, "wn.csv", "assessment,weight\nhw,-20\nmid,30\nfinal,50\n")))
        res["P16_zero_weights"] = clean_err(invoke(side, s, write(d, "wz.csv", "assessment,weight\nhw,0\nmid,0\nfinal,0\n")))
        res["P17_empty_csv"] = clean_err(invoke(side, write(d, "e.csv", ""), w))
        rr = invoke(side, write(d, "rg.csv", "student,hw,mid,final\nAnn,90,80\nBob,100,100,100\n"), w)
        res["P18_ragged_row_flagged"] = "Traceback" not in rr.stderr and (rr.returncode != 0 or rr.stderr.strip() != "")
        ro = invoke(side, write(d, "o.csv", "student,hw,mid,final\nAnn,900,80,70\nBob,100,100,100\n"), w)
        res["P19_out_of_range_flagged"] = "Traceback" not in ro.stderr and (ro.returncode != 0 or ro.stderr.strip() != "")
        rb = invoke(side, write(d, "bin.csv", b"student,hw,mid,final\n\xff\xfe,90,80,70\n", True), w)
        res["P20_non_utf8_no_traceback"] = "Traceback" not in rb.stderr and rb.returncode != 0
        r1 = invoke(side, write(d, "one.csv", "student,hw,mid,final\nAnn,90,80,70\n"), w)
        res["P21_single_student"] = r1.returncode == 0 and "Traceback" not in r1.stderr and "77.00" in r1.stdout
        rn = invoke(side, s, write(d, "wnan.csv", "assessment,weight\nhw,nan\nmid,30\nfinal,50\n"))
        res["P22_nan_weight"] = clean_err(rn)
    return {k: "pass" if v else "fail" for k, v in res.items()}

out = {"A": probes("A"), "B": probes("B")}
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
