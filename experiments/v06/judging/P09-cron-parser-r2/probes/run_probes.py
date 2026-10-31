import json, subprocess, sys, datetime as dt, tempfile, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(side, *args):
    with tempfile.TemporaryDirectory() as td:
        p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, side, "cron_parser.py"), *args],
                           capture_output=True, text=True, cwd=td, timeout=60)
    return p.returncode, p.stdout, p.stderr

def ref_next(pred, n, now):
    t = now.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    out = []
    while len(out) < n:
        if pred(t): out.append(t)
        t += dt.timedelta(minutes=1)
    return out

def times(stdout):
    res = []
    for line in stdout.splitlines():
        line = line.strip()
        try:
            res.append(dt.datetime.strptime(line[:16], "%Y-%m-%d %H:%M"))
        except ValueError:
            pass
    return res

def next_ok(side, expr, n, pred, nflag=True):
    before = dt.datetime.now()
    args = ["next", expr] + (["-n", str(n)] if nflag else [])
    rc, out, err = run(side, *args)
    after = dt.datetime.now()
    got = times(out)
    return rc == 0 and (got == ref_next(pred, n, before) or got == ref_next(pred, n, after))

def clean_err(rc, out, err):
    return rc != 0 and "Traceback" not in err and len((out + err).strip()) > 0

dow = lambda t: t.isoweekday() % 7
P = {
 "P01_wrong_field_count": lambda s: clean_err(*run(s, "validate", "* * * *")) and clean_err(*run(s, "validate", "* * * * * *")),
 "P02_validate_explains_fields": lambda s: (lambda r: r[0]==0 and all(k in r[1].lower() for k in ["minute","hour","month"]) and ("day-of-month" in r[1].lower() or "day of month" in r[1].lower()) and ("day-of-week" in r[1].lower() or "day of week" in r[1].lower()))(run(s, "validate", "*/15 9-17 1,15 jan-mar mon-fri")),
 "P03_validate_explains_values": lambda s: (lambda r: r[0]==0 and "15" in r[1] and "45" in r[1] and "9" in r[1] and "17" in r[1])(run(s, "validate", "*/15 9-17 * * *")),
 "P04_out_of_range_minute": lambda s: clean_err(*run(s, "validate", "60 * * * *")),
 "P05_out_of_range_hour": lambda s: clean_err(*run(s, "validate", "0 24 * * *")),
 "P06_out_of_range_dom0": lambda s: clean_err(*run(s, "validate", "0 0 0 * *")),
 "P07_out_of_range_month13": lambda s: clean_err(*run(s, "validate", "0 0 1 13 *")),
 "P08_out_of_range_dow8": lambda s: clean_err(*run(s, "validate", "0 0 * * 8")),
 "P09_bad_token": lambda s: clean_err(*run(s, "validate", "abc * * * *")),
 "P10_step_zero": lambda s: clean_err(*run(s, "validate", "*/0 * * * *")),
 "P11_reversed_range": lambda s: clean_err(*run(s, "validate", "0 0 * * 5-1")),
 "P12_empty_list_item": lambda s: clean_err(*run(s, "validate", "1,,2 * * * *")),
 "P13_next_star_n3": lambda s: next_ok(s, "* * * * *", 3, lambda t: True),
 "P14_next_default_count_is_positive": lambda s: (lambda r: r[0]==0 and len(times(r[1]))>=1)(run(s, "next", "* * * * *")),
 "P15_next_list": lambda s: next_ok(s, "5,35 * * * *", 4, lambda t: t.minute in (5,35)),
 "P16_next_range_step": lambda s: next_ok(s, "10-50/20 */6 * * *", 6, lambda t: t.minute in (10,30,50) and t.hour % 6 == 0),
 "P17_next_month_names": lambda s: next_ok(s, "0 12 1 jan,JUL *", 3, lambda t: t.minute==0 and t.hour==12 and t.day==1 and t.month in (1,7)),
 "P18_next_dow_names_range": lambda s: next_ok(s, "30 8 * * MON-FRI", 6, lambda t: t.minute==30 and t.hour==8 and dow(t) in (1,2,3,4,5)),
 "P19_dow7_sunday": lambda s: next_ok(s, "0 0 * * 7", 2, lambda t: t.minute==0 and t.hour==0 and dow(t)==0),
 "P20_dom_dow_or": lambda s: next_ok(s, "0 0 13 * 5", 5, lambda t: t.minute==0 and t.hour==0 and (t.day==13 or dow(t)==5)),
 "P21_feb30_not_produced": lambda s: (lambda r: r[0]!=0 and "Traceback" not in r[2] and not times(r[1]))(run(s, "next", "0 0 30 2 *")),
 "P22_feb30_validate_reports": lambda s: (lambda r: "Traceback" not in r[2] and ("never" in (r[1]+r[2]).lower() or "no valid" in (r[1]+r[2]).lower() or "not exist" in (r[1]+r[2]).lower() or r[0]!=0))(run(s, "validate", "0 0 30 2 *")),
 "P23_feb29_leap": lambda s: next_ok(s, "0 0 29 2 *", 2, lambda t: t.minute==0 and t.hour==0 and t.month==2 and t.day==29),
 "P24_dom31_skips_short_months": lambda s: next_ok(s, "0 0 31 * *", 4, lambda t: t.minute==0 and t.hour==0 and t.day==31),
 "P25_n_zero_rejected": lambda s: clean_err(*run(s, "next", "* * * * *", "-n", "0")),
 "P26_unicode_digit_clean": lambda s: (lambda r: r[0]!=0 and "Traceback" not in r[2])(run(s, "validate", "² * * * *")),
 "P27_unicode_step_clean": lambda s: (lambda r: r[0]!=0 and "Traceback" not in r[2])(run(s, "validate", "*/² * * * *")),
 "P28_invalid_next_expr_clean": lambda s: clean_err(*run(s, "next", "61 * * * *")),
 "P29_name_in_minute_rejected": lambda s: clean_err(*run(s, "validate", "jan * * * *")),
 "P30_stdlib_single_file": lambda s: os.path.isfile(os.path.join(ROOT, s, "cron_parser.py")),
}
res = {}
for side in ["A", "B"]:
    res[side] = {}
    for k, f in P.items():
        try: ok = f(side)
        except Exception as e: ok = False; print(side, k, "EXC", e)
        res[side][k] = "pass" if ok else "fail"
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for side in res:
    print(side, sum(v=="pass" for v in res[side].values()), [k for k,v in res[side].items() if v=="fail"])
