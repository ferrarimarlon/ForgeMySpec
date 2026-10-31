import json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = "2026-10"

def adapter(side):
    if side == "A":
        return dict(
            budget=lambda c, a: ["set-budget", M, c, a],
            add=lambda a, c, d, n=None: ["add", a, c, d] + ([n] if n else []),
            report=lambda: ["report", M])
    return dict(
        budget=lambda c, a: ["set-budget", c, a],
        add=lambda a, c, d, n=None: ["add", a, c, "--date", d] + (["--note", n] if n else []),
        report=lambda: ["report", "--month", M])

class Ctx:
    def __init__(self, side):
        self.side, self.ad = side, adapter(side)
        self.tmp = tempfile.mkdtemp()
        self.file = os.path.join(self.tmp, "data.json")
    def run(self, argv):
        p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, self.side, "budget_tracker.py"),
                            "--file", self.file] + argv, cwd=self.tmp, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    def budget(self, c, a): return self.run(self.ad["budget"](c, a))
    def add(self, *a): return self.run(self.ad["add"](*a))
    def report(self): return self.run(self.ad["report"]())
    def raw(self):
        return open(self.file).read() if os.path.exists(self.file) else None

def no_tb(r): return "Traceback" not in r[2]

def p_single_file_stdlib(c):
    src = open(os.path.join(ROOT, c.side, "budget_tracker.py")).read()
    import ast
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom): mods.add(n.module.split(".")[0])
    return mods <= set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else mods <= {"argparse","json","os","sys","tempfile","datetime","decimal"}

def p_set_budget(c):
    r = c.budget("food", "100")
    return r[0] == 0 and "100" in c.raw()

def p_record_expense_fields(c):
    c.budget("food", "100")
    r = c.add("12.50", "food", "2026-10-05", "lunch")
    if r[0] != 0: return False
    d = json.loads(c.raw())
    s = json.dumps(d)
    return "12.5" in s and "2026-10-05" in s and "lunch" in s and "food" in s

def p_persist_across_runs(c):
    c.budget("food", "100"); c.add("10", "food", "2026-10-05", "a"); c.add("15", "food", "2026-10-06", "b")
    r = c.report()
    return r[0] == 0 and "25" in r[1]

def p_reject_unknown_category(c):
    c.budget("food", "100"); before = c.raw()
    r = c.add("10", "travel", "2026-10-05")
    return r[0] != 0 and no_tb(r) and c.raw() == before

def p_reject_unknown_no_budgets(c):
    r = c.add("10", "food", "2026-10-05")
    return r[0] != 0 and no_tb(r)

def _reject_amount(c, amt):
    c.budget("food", "100"); before = c.raw()
    r = c.add(amt, "food", "2026-10-05")
    return r[0] != 0 and no_tb(r) and c.raw() == before

def p_reject_amount_text(c): return _reject_amount(c, "abc")
def p_reject_amount_negative(c): return _reject_amount(c, "-5")
def p_reject_amount_zero(c): return _reject_amount(c, "0")
def p_reject_amount_nan(c): return _reject_amount(c, "nan")
def p_reject_amount_inf(c): return _reject_amount(c, "inf")
def p_reject_amount_empty(c): return _reject_amount(c, "")
def p_huge_amount_no_crash(c):
    c.budget("food", "100")
    r = c.add("1e30", "food", "2026-10-05")
    return no_tb(r)
def p_reject_budget_invalid(c):
    r = c.budget("food", "-1")
    return r[0] != 0 and no_tb(r)

def p_reject_invalid_date(c):
    c.budget("food", "100"); before = c.raw()
    r = c.add("10", "food", "2026-13-45")
    return r[0] != 0 and no_tb(r) and c.raw() == before

def p_report_per_category(c):
    c.budget("food", "100"); c.budget("rent", "1000")
    c.add("30", "food", "2026-10-05"); c.add("200", "rent", "2026-10-01")
    r = c.report()
    lines = r[1].splitlines()
    f = [l for l in lines if l.strip().startswith("food")]
    g = [l for l in lines if l.strip().startswith("rent")]
    return r[0] == 0 and f and "30" in f[0] and "100" in f[0] and g and "200" in g[0] and "1000" in g[0]

def p_report_month_isolation(c):
    c.budget("food", "100"); c.add("30", "food", "2026-10-05")
    c.add("50", "food", "2026-09-05")
    r = c.report()
    f = [l for l in r[1].splitlines() if l.strip().startswith("food")]
    return f and "30" in f[0] and "80" not in f[0]

def _alerts(out):
    o = out.lower()
    return ("80" in o and ("alert" in o or "warn" in o)), ("100" in o and ("alert" in o or "exceed" in o))

def p_alert_below_80_none(c):
    c.budget("food", "100"); r = c.add("79.99", "food", "2026-10-05")
    rr = c.report()
    return r[0] == 0 and "alert" not in (r[1]+rr[1]).lower() and "warn" not in (r[1]+rr[1]).lower()

def p_alert_80_on_add(c):
    c.budget("food", "100"); r = c.add("80", "food", "2026-10-05")
    w, f = _alerts(r[1]); return r[0] == 0 and w and "100%" not in r[1].replace("of 100.00","")

def p_alert_80_in_report(c):
    c.budget("food", "100"); c.add("85", "food", "2026-10-05")
    r = c.report(); w, _ = _alerts(r[1]); return w

def p_alert_100_on_add(c):
    c.budget("food", "100"); c.add("50", "food", "2026-10-05"); r = c.add("50", "food", "2026-10-06")
    _, f = _alerts(r[1]); return r[0] == 0 and f

def p_alert_100_over_in_report(c):
    c.budget("food", "100"); c.add("150", "food", "2026-10-05")
    r = c.report(); _, f = _alerts(r[1]); return f

def p_corrupt_file_no_tb(c):
    open(c.file, "w").write("{not json")
    r = c.report(); return r[0] != 0 and no_tb(r)

def p_wrong_shape_file_no_tb(c):
    open(c.file, "w").write('{"budgets": [], "expenses": {}}')
    r = c.report(); return no_tb(r)

def p_invalid_month_report(c):
    r = c.run(["report", "2026-99"] if c.side == "A" else ["report", "--month", "2026-99"])
    return r[0] != 0 and no_tb(r)

PROBES = {k: v for k, v in globals().items() if k.startswith("p_")}
res = {}
for side in ("A", "B"):
    res[side] = {}
    for name, fn in PROBES.items():
        try: ok = bool(fn(Ctx(side)))
        except Exception as e: ok = False; print(side, name, "EXC", e)
        res[side][name[2:]] = "pass" if ok else "fail"
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for n in PROBES: print(f"{n[2:]:30} A={res['A'][n[2:]]:5} B={res['B'][n[2:]]}")
