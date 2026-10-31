"""Black-box probes. Usage: python3 -I run_probes.py <dir containing cron_parser.py>"""
import json, subprocess, sys, re, os, tempfile, ast
from datetime import datetime, timedelta

SIDE_DIR = os.path.abspath(sys.argv[1])
PROG = os.path.join(SIDE_DIR, "cron_parser.py")

def run(*args, timeout=30):
    with tempfile.TemporaryDirectory() as td:
        try:
            p = subprocess.run([sys.executable, "-I", PROG, *args], capture_output=True,
                               text=True, timeout=timeout, cwd=td)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return "timeout", "", ""

DT = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})")
def times(out):
    return [datetime.strptime(f"{a} {b}", "%Y-%m-%d %H:%M") for a, b in DT.findall(out)]

# independent reference matcher
NAMES = {**{m: i+1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())},}
DNAMES = {d: i for i, d in enumerate("sun mon tue wed thu fri sat".split())}
RANGES = [(0,59),(0,23),(1,31),(1,12),(0,7)]
def fset(text, idx):
    lo, hi = RANGES[idx]; names = NAMES if idx==3 else DNAMES if idx==4 else {}
    out=set()
    for part in text.split(","):
        b, _, s = part.partition("/"); s = int(s) if s else 1
        conv = lambda x: names.get(x.lower(), None) if x.lower() in names else int(x)
        if b=="*": a,e=lo,hi
        elif "-" in b: x,y=b.split("-"); a,e=conv(x),conv(y)
        else: a=conv(b); e = hi if "/" in part else a
        out |= set(range(a,e+1,s))
    if idx==4: out={v%7 for v in out}
    return out
def ref_next(expr, now, n):
    f = expr.split(); sets=[fset(x,i) for i,x in enumerate(f)]
    domr = not f[2].startswith("*"); dowr = not f[4].startswith("*")
    t = now.replace(second=0, microsecond=0)+timedelta(minutes=1)
    d = t.replace(hour=0, minute=0); res=[]
    for _ in range(366*30):
        if d.month in sets[3]:
            dm = d.day in sets[2]; dw = (d.isoweekday()%7) in sets[4]
            ok = (dm or dw) if (domr and dowr) else (dm and dw)
            if ok:
                for h in sorted(sets[1]):
                    for m in sorted(sets[0]):
                        x = d.replace(hour=h, minute=m)
                        if x >= t:
                            res.append(x)
                            if len(res)==n: return res
        d += timedelta(days=1)
    return res

def check_next(expr, n):
    before = datetime.now()
    args = ["next", expr] + (["-n", str(n)] if n is not None else [])
    rc, out, err = run(*args)
    if rc != 0: return False, f"rc={rc} err={err[:200]}"
    got = times(out)
    exp = ref_next(expr, before, n if n is not None else len(got) or 1)
    exp2 = ref_next(expr, datetime.now(), n if n is not None else len(got) or 1)
    ok = got == exp or got == exp2
    return ok, f"got={[str(x) for x in got[:6]]} exp={[str(x) for x in exp[:6]]}"

STDLIB = getattr(sys, 'stdlib_module_names', None) or {'argparse','calendar','sys','datetime','re','os','time','itertools','functools','typing','collections','dataclasses','enum','__future__','unittest','math','json'}
results = {}; details = {}
def probe(pid, fn):
    try:
        ok, d = fn()
    except Exception as e:
        ok, d = False, f"probe exception {e!r}"
    results[pid] = "pass" if ok else "fail"; details[pid] = d

def valid_ok(expr, must=()):
    rc, out, err = run("validate", expr)
    ok = rc == 0 and all(re.search(m, out, re.I) for m in must)
    return ok, f"rc={rc} out={out[:300]!r} err={err[:200]!r}"
def invalid_ok(expr):
    rc, out, err = run("validate", expr)
    ok = rc not in (0, "timeout") and "Traceback" not in err and len((out+err).strip())>0
    return ok, f"rc={rc} out={out[:150]!r} err={err[:200]!r}"

# R1/R2
probe("P01_single_file_stdlib", lambda: (lambda src: (all(
    (n.module if isinstance(n, ast.ImportFrom) else a.name).split(".")[0] in STDLIB
    for n in ast.walk(ast.parse(src)) if isinstance(n,(ast.Import,ast.ImportFrom))
    for a in (n.names if isinstance(n, ast.Import) else [n])), "imports checked"))(open(PROG).read()))
# R3
probe("P02_wrong_field_count_4", lambda: invalid_ok("* * * *"))
probe("P03_wrong_field_count_6", lambda: invalid_ok("* * * * * *"))
# R11 explain
probe("P04_validate_explains_5_fields", lambda: valid_ok("*/15 9-17 * * 1-5",
      ["minute", "hour", "day.of.month|day of month|dom", "month", "day.of.week|weekday|dow"]))
probe("P05_validate_list", lambda: valid_ok("0,15,30 * * * *", ["15"]))
probe("P06_validate_month_names", lambda: valid_ok("0 0 1 jan-mar *", ["jan"]))
probe("P07_validate_dow_names", lambda: valid_ok("0 0 * * MON-FRI", ["mon"]))
probe("P08_validate_dow_7_sunday", lambda: valid_ok("0 0 * * 7", ["sun"]))
# R10, R12
for pid, e in [("P09_minute_60", "60 * * * *"), ("P10_hour_24", "0 24 * * *"),
               ("P11_dom_0", "0 0 0 * *"), ("P12_month_13", "0 0 1 13 *"),
               ("P13_dow_8", "0 0 * * 8"), ("P14_bad_name", "0 0 * foo *"),
               ("P15_step_zero", "*/0 * * * *"), ("P16_reversed_range", "0 0 * * 5-1"),
               ("P17_garbage", "a b c d e"), ("P18_empty_list_item", "1,,2 * * * *"),
               ("P19_unicode_digit", "² * * * *"), ("P20_negative", "-1 * * * *"),
               ("P21_empty_expr", "")]:
    probe(pid, lambda e=e: invalid_ok(e))
probe("P22_next_invalid_expr_errors", lambda: (lambda r: (r[0] not in (0,"timeout") and "Traceback" not in r[2], str(r)[:200]))(run("next", "61 * * * *")))
# R13/R14/R15
probe("P23_next_default", lambda: (lambda r: (r[0]==0 and len(times(r[1]))>=1, str(r)[:200]))(run("next", "*/5 * * * *")))
probe("P24_next_n5_every_minute", lambda: check_next("* * * * *", 5))
probe("P25_next_n10_steps_ranges", lambda: check_next("*/15 9-17 * * mon-fri", 10))
probe("P26_next_month_names", lambda: check_next("30 6 1 jan,jul *", 3))
probe("P27_next_dom_dow_or", lambda: check_next("0 12 13 * fri", 6))
probe("P28_next_dom_star_step_dow", lambda: check_next("0 0 */2 * mon", 4))
probe("P29_next_range_step", lambda: check_next("10-50/20 2 * * *", 6))
probe("P30_next_single_step_5_10", lambda: check_next("5/20 * * * *", 4))
probe("P31_next_dow_7", lambda: check_next("0 0 * * 7", 3))
probe("P32_next_31st_skips_short_months", lambda: check_next("0 0 31 * *", 7))
# R16
probe("P33_feb29_leap", lambda: check_next("0 0 29 2 *", 2))
probe("P34_feb29_n5_long_horizon", lambda: check_next("0 0 29 2 *", 5))
def feb30():
    rc, out, err = run("next", "0 0 30 2 *")
    ok = rc != "timeout" and "Traceback" not in err and not times(out) and (out+err).strip()
    return bool(ok), f"rc={rc} out={out[:150]!r} err={err[:200]!r}"
probe("P35_next_feb30_clean", feb30)
def feb30v():
    rc, out, err = run("validate", "0 0 30 2 *")
    txt = (out+err).lower()
    ok = rc != "timeout" and "Traceback" not in err and any(k in txt for k in ["never", "no ", "invalid", "nonexist", "impossible"])
    return ok, f"rc={rc} out={out[:200]!r} err={err[:200]!r}"
probe("P36_validate_feb30_flagged", feb30v)
probe("P37_apr31_never", lambda: (lambda r: (r[0]!="timeout" and "Traceback" not in r[2] and not times(r[1]), str(r)[:200]))(run("next", "0 0 31 4 *")))
probe("P38_feb30_or_31jan_ok", lambda: check_next("0 0 30,31 1,2 *", 3))
# R17
for pid, nv in [("P39_n_zero", "0"), ("P40_n_negative", "-3"), ("P41_n_nonint", "abc")]:
    probe(pid, lambda nv=nv: (lambda r: (r[0] not in (0,"timeout") and "Traceback" not in r[2], str(r)[:200]))(run("next", "* * * * *", "-n", nv)))
probe("P42_strictly_after_now", lambda: (lambda r: (all(t > datetime.now()-timedelta(minutes=1) for t in times(r[1])) and len(times(r[1]))==3, str(r)[:200]))(run("next", "* * * * *", "-n", "3")))

print(json.dumps({"results": results, "details": details}, indent=1))
