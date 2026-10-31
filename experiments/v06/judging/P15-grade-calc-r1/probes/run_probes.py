"""Black-box probes. Only invocation/weights-file format is adapted per side."""
import ast, json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def wfile(side, pairs):
    if side == "A":
        return "".join(f"{k},{v}\n" for k, v in pairs)
    return "assessment,weight\n" + "".join(f"{k},{v}\n" for k, v in pairs)

def run(side, scores, pairs, scores_path=None):
    d = tempfile.mkdtemp()
    sp = scores_path or os.path.join(d, "s.csv")
    if scores_path is None:
        open(sp, "w").write(scores)
    wp = os.path.join(d, "w.csv"); open(wp, "w").write(wfile(side, pairs))
    prog = os.path.join(ROOT, side, "grade_calc.py")
    cmd = [sys.executable, "-I", prog, sp, "--weights-file", wp] if side == "A" else [sys.executable, "-I", prog, sp, wp]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=d, timeout=30)
    return p.returncode, p.stdout, p.stderr

def row(out, name):
    for l in out.splitlines():
        if l.strip().startswith(name + " "):
            return l
    return ""

def nums(s): return [float(x) for x in re.findall(r"-?\d+\.\d+", s)]

def stat(out, key):
    for l in out.splitlines():
        if l.strip().lower().startswith(key):
            n = nums(l); return n[0] if n else None

def clean_err(r): return r[0] != 0 and "Traceback" not in r[2] + r[1]

W = [("hw", 30), ("exam", 70)]
BASIC = "student,hw,exam\nAna,100,50\nBo,80,90\nCy,40,60\nDi,95,95\n"
# finals: Ana 65.00, Bo 87.00, Cy 54.00, Di 95.00
P = {}
def probe(pid):
    def deco(f): P[pid] = f; return f
    return deco

@probe("P01_runs")
def _(s): return run(s, BASIC, W)[0] == 0
@probe("P02_weighted_final")
def _(s):
    o = run(s, BASIC, W)[1]
    return 65.0 in nums(row(o, "Ana")) and 87.0 in nums(row(o, "Bo")) and 54.0 in nums(row(o, "Cy"))
@probe("P03_normalize_small")
def _(s):
    o = run(s, BASIC, [("hw", 3), ("exam", 7)])[1]
    return 65.0 in nums(row(o, "Ana")) and 87.0 in nums(row(o, "Bo"))
@probe("P04_normalize_large")
def _(s):
    o = run(s, BASIC, [("hw", 60), ("exam", 140)])[1]
    return 65.0 in nums(row(o, "Ana")) and 95.0 in nums(row(o, "Di"))
@probe("P05_letter")
def _(s):
    o = run(s, BASIC, W)[1]
    return re.search(r"\bA\b", row(o, "Di")) and re.search(r"\bF\b", row(o, "Cy")) and re.search(r"\bB[+\-]?(\s|$)", row(o, "Bo"))
@probe("P06_gpa")
def _(s):
    o = run(s, BASIC, W)[1]
    return 4.0 in nums(row(o, "Di")) and 0.0 in nums(row(o, "Cy"))
@probe("P07_mean")
def _(s): return stat(run(s, BASIC, W)[1], "mean") == 75.25
@probe("P08_median_even")
def _(s): return stat(run(s, BASIC, W)[1], "median") == 76.0
@probe("P09_stddev")
def _(s):
    v = stat(run(s, BASIC, W)[1], "std")
    return v in (16.47, 19.02)  # population or sample
@probe("P10_high_low")
def _(s):
    o = run(s, BASIC, W)[1]
    return stat(o, "highest") == 95.0 and stat(o, "lowest") == 54.0
@probe("P11_missing_file")
def _(s): return clean_err(run(s, None, W, scores_path="/nonexistent/x.csv"))
@probe("P12_nonnumeric_score")
def _(s): return clean_err(run(s, "student,hw,exam\nAna,abc,50\n", W))
@probe("P13_nan_score")
def _(s): return clean_err(run(s, "student,hw,exam\nAna,nan,50\n", W))
@probe("P14_negative_weight")
def _(s): return clean_err(run(s, BASIC, [("hw", -10), ("exam", 70)]))
@probe("P15_zero_weights")
def _(s): return clean_err(run(s, BASIC, [("hw", 0), ("exam", 0)]))
@probe("P16_weight_unknown_column")
def _(s): return clean_err(run(s, BASIC, [("hw", 30), ("quiz", 70)]))
@probe("P17_score_over_100_not_silent")
def _(s):
    r = run(s, "student,hw,exam\nAna,150,50\n", W)
    return clean_err(r)
@probe("P18_header_only")
def _(s): return clean_err(run(s, "student,hw,exam\n", W))
@probe("P19_short_row_no_crash")
def _(s):
    r = run(s, "student,hw,exam\nAna,100\nBo,80,90\n", W)
    return "Traceback" not in r[2] and (r[0] != 0 or "missing" in (r[1] + r[2]).lower())
@probe("P20_stdlib_single_file")
def _(s):
    src = open(os.path.join(ROOT, s, "grade_calc.py")).read()
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    STD = {"argparse","csv","statistics","sys","math","os","re","json","io","decimal","fractions","pathlib","typing","dataclasses","collections","itertools","functools","__future__"}
    return all(m in STD for m in mods)
@probe("P21_single_student_stats")
def _(s):
    r = run(s, "student,hw,exam\nAna,100,50\n", W)
    return r[0] == 0 and stat(r[1], "mean") == 65.0
@probe("P22_letter_boundary_90")
def _(s):
    o = run(s, "student,hw,exam\nEd,90,90\nFi,89,89\n", W)[1]
    return re.search(r"\bA-?(\s|$)", row(o, "Ed")) and not re.search(r"\bA", row(o, "Fi").split(None, 1)[1])

res = {}
for side in ("A", "B"):
    res[side] = {}
    for pid, f in P.items():
        try: ok = bool(f(side))
        except Exception as e: ok = False
        res[side][pid] = "pass" if ok else "fail"
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for side in res:
    print(side, sum(v == "pass" for v in res[side].values()), [k for k, v in res[side].items() if v == "fail"])
