import json, os, subprocess, sys, tempfile, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def mk(side):
    script = os.path.join(ROOT, side, "budget_tracker.py")
    d = tempfile.mkdtemp()
    f = os.path.join(d, "data.json")
    def run(*a):
        p = subprocess.run([sys.executable, "-I", script, "--file", f, *a], capture_output=True, text=True, cwd=d)
        return p.returncode, p.stdout, p.stderr
    def raw():
        return open(f).read() if os.path.exists(f) else None
    return run, raw, f, script

def probes(side):
    res = {}; detail = {}
    def P(name, fn):
        try:
            ok = bool(fn())
        except Exception as e:
            ok = False; detail[name] = repr(e)
        res[name] = "pass" if ok else "fail"
    def p_budget():
        run, raw, f, _ = mk(side)
        c, o, e = run("set-budget", "food", "100")
        return c == 0 and json.loads(raw())  # file exists & JSON
    P("P01_set_budget_persists", p_budget)
    def p_add():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100")
        c, o, e = run("add", "12.50", "food", "--date", "2026-03-05", "--note", "lunch")
        s = raw()
        return c == 0 and all(x in s for x in ["12.5", "food", "2026-03-05", "lunch"])
    P("P02_add_expense_all_fields_json", p_add)
    def p_unknown():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100"); before = raw()
        c, o, e = run("add", "5", "games", "--date", "2026-03-05")
        return c != 0 and raw() == before and "Traceback" not in e
    P("P03_reject_unknown_category", p_unknown)
    def p_bad(v):
        def fn():
            run, raw, f, _ = mk(side)
            run("set-budget", "food", "100"); before = raw()
            c, o, e = run("add", v, "food", "--date", "2026-03-05")
            return c != 0 and raw() == before and "Traceback" not in e
        return fn
    for i, v in enumerate(["abc", "0", "-5", "nan", "inf", "", "1e999"]):
        P(f"P04_reject_amount_{i}_{v or 'empty'}", p_bad(v))
    def p_bad_budget():
        run, raw, f, _ = mk(side)
        r = [run("set-budget", "x", v)[0] for v in ["-1", "abc", "nan"]]
        return all(c != 0 for c in r) and raw() is None
    P("P05_reject_invalid_budget_amount", p_bad_budget)
    def p_bad_date():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100"); before = raw()
        c, o, e = run("add", "5", "food", "--date", "2026-13-40")
        return c != 0 and raw() == before and "Traceback" not in e
    P("P06_reject_invalid_date", p_bad_date)
    def p_report():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100"); run("set-budget", "fun", "50")
        run("add", "25", "food", "--date", "2026-03-05")
        run("add", "70", "food", "--date", "2026-04-05")
        c, o, e = run("report", "--month", "2026-03")
        food = [l for l in o.splitlines() if l.strip().startswith("food")]
        fun = [l for l in o.splitlines() if l.strip().startswith("fun")]
        return c == 0 and food and "25" in food[0] and "100" in food[0] and fun and "50" in fun[0] and "95" not in food[0]
    P("P07_report_per_category_monthly", p_report)
    def p_80_add():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100")
        _, o1, _ = run("add", "79.99", "food", "--date", "2026-03-01")
        _, o2, _ = run("add", "0.01", "food", "--date", "2026-03-02")
        return "80" not in o1.replace("79.99","") and ("80" in o2 or "warn" in o2.lower())  and ("WARN" in o2.upper())
    P("P08_alert_80_on_add_boundary", p_80_add)
    def p_100_add():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100")
        _, o1, _ = run("add", "99.99", "food", "--date", "2026-03-01")
        _, o2, _ = run("add", "0.01", "food", "--date", "2026-03-02")
        return "100" in o2 and "ALERT" in o2.upper() and "ALERT" not in o1.upper()
    P("P09_alert_100_on_add_boundary", p_100_add)
    def p_rep_alerts():
        run, raw, f, _ = mk(side)
        run("set-budget", "a", "100"); run("set-budget", "b", "100"); run("set-budget", "c", "100")
        run("add", "85", "a", "--date", "2026-03-01")
        run("add", "120", "b", "--date", "2026-03-01")
        run("add", "10", "c", "--date", "2026-03-01")
        c, o, e = run("report", "--month", "2026-03")
        lines = o.splitlines()
        al = [l for l in lines if "WARN" in l.upper() or "ALERT" in l.upper()]
        return c == 0 and any(l.strip().startswith("a") or " a" in l for l in al if "WARN" in l.upper()) and any("b" in l for l in al if "ALERT" in l.upper() and "WARN" not in l.upper()) and not any(l.strip().startswith("c") for l in al)
    P("P10_report_alerts_80_100", p_rep_alerts)
    def p_month_isolation():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100")
        run("add", "90", "food", "--date", "2026-02-28")
        _, o, _ = run("add", "10", "food", "--date", "2026-03-01")
        return "WARN" not in o.upper() and "ALERT" not in o.upper()
    P("P11_alerts_per_month", p_month_isolation)
    def p_bad_month():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100")
        c, o, e = run("report", "--month", "2026-13")
        return c != 0 and "Traceback" not in e
    P("P12_reject_invalid_report_month", p_bad_month)
    def p_corrupt():
        run, raw, f, _ = mk(side)
        open(f, "w").write("{not json")
        c, o, e = run("add", "5", "food")
        return c != 0 and "Traceback" not in e and raw() == "{not json"
    P("P13_corrupt_file_clean_error", p_corrupt)
    def p_wrongshape():
        run, raw, f, _ = mk(side)
        open(f, "w").write('{"budgets": ["food"], "expenses": []}')
        c, o, e = run("report")
        return c != 0 and "Traceback" not in e
    P("P14_wrong_shape_file_clean_error", p_wrongshape)
    def p_stdlib():
        _, _, _, s = mk(side)
        tree = ast.parse(open(s).read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom): mods.add(n.module.split(".")[0])
        return mods <= {"argparse","json","math","os","sys","tempfile","datetime","decimal","ast","re","pathlib","typing","collections","calendar"}
    P("P15_stdlib_only", p_stdlib)
    def p_default_date():
        run, raw, f, _ = mk(side)
        import datetime
        run("set-budget", "food", "100")
        c, o, e = run("add", "5", "food")
        return c == 0 and datetime.date.today().isoformat() in raw()
    P("P16_default_date_today", p_default_date)
    def p_persist_across():
        run, raw, f, _ = mk(side)
        run("set-budget", "food", "100"); run("set-budget", "rent", "1000")
        run("add", "5", "food", "--date", "2026-03-01"); run("add", "7", "food", "--date", "2026-03-02")
        d = json.loads(raw())
        return len(d["expenses"]) == 2 and len(d["budgets"]) == 2
    P("P17_accumulates_records", p_persist_across)
    def p_whitespace_cat():
        run, raw, f, _ = mk(side)
        run("set-budget", " food ", "100")
        c, o, e = run("add", "5", " food ", "--date", "2026-03-01")
        return c == 0
    P("P18_category_whitespace_consistent", p_whitespace_cat)
    return res, detail

out = {}; details = {}
for s in ("A", "B"):
    out[s], details[s] = probes(s)
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(out, indent=1)); print(details)
