import json, os, subprocess, sys, tempfile, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def mk(side):
    src = os.path.join(ROOT, side, "budget_tracker.py")
    def run(f, *a):
        p = subprocess.run([sys.executable, "-I", src, "--file", f, *a], capture_output=True, text=True, cwd=os.path.dirname(f))
        return p.returncode, p.stdout, p.stderr
    return src, run

def fresh():
    d = tempfile.mkdtemp(); return os.path.join(d, "data.json")

def unchanged(run, f, argv):
    before = open(f).read()
    c, o, e = run(f, *argv)
    return c != 0 and "Traceback" not in e and open(f).read() == before

def probes(side):
    src, run = mk(side); R = {}
    R["P01_single_file_exists"] = os.path.isfile(src)
    tree = ast.parse(open(src).read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    R["P02_stdlib_only"] = all(m in sys.stdlib_module_names for m in mods) if hasattr(sys, "stdlib_module_names") else mods <= {"argparse","json","os","sys","tempfile","datetime","decimal"}
    f = fresh()
    c, o, e = run(f, "--help"); R["P03_help"] = c == 0
    c, o, e = run(f, "set-budget", "food", "100")
    R["P04_set_budget"] = c == 0 and os.path.exists(f)
    c, o, e = run(f, "add", "10.50", "food", "--date", "2026-03-05", "--note", "lunch")
    d = json.load(open(f))
    exp = d.get("expenses", [])
    R["P05_expense_persisted_all_fields"] = c == 0 and len(exp) == 1 and all(
        str(v) in json.dumps(exp[0]) for v in ["10.5", "food", "2026-03-05", "lunch"])
    R["P06_unknown_category_rejected"] = unchanged(run, f, ["add", "5", "travel", "--date", "2026-03-05"])
    for i, bad in enumerate(["abc", "0", "-5", "nan", "inf", "", "1e400", "1e30"]):
        R[f"P07_invalid_amount_{i}_{bad or 'empty'}"] = unchanged(run, f, ["add", "--date", "2026-03-05", "--", bad, "food"])
    R["P08_invalid_budget_amount"] = unchanged(run, f, ["set-budget", "--", "food", "-1"])
    R["P09_invalid_date"] = unchanged(run, f, ["add", "5", "food", "--date", "2026-02-30"])
    # report
    run(f, "set-budget", "fun", "50")
    run(f, "add", "20", "food", "--date", "2026-03-20")
    run(f, "add", "999", "food", "--date", "2026-04-01")
    c, o, e = run(f, "report", "--month", "2026-03")
    food = [l for l in o.splitlines() if l.strip().startswith("food")]
    fun = [l for l in o.splitlines() if l.strip().startswith("fun")]
    R["P10_report_per_category_vs_budget"] = c == 0 and bool(food) and "30.50" in food[0] and "100.00" in food[0] and bool(fun)
    R["P11_report_month_filter"] = "999" not in (food[0] if food else "999")
    R["P12_report_no_alert_below_80"] = "80%" not in o.replace("Used", "") and "100%" not in o
    # 80% alert on add
    f2 = fresh(); run(f2, "set-budget", "food", "100")
    run(f2, "add", "50", "food", "--date", "2026-03-01")
    c, o, e = run(f2, "add", "30", "food", "--date", "2026-03-02")
    R["P13_add_alert_at_exactly_80"] = c == 0 and "80%" in (o + e)
    c, o, e = run(f2, "report", "--month", "2026-03")
    R["P14_report_alert_80"] = "80%" in o + e and any(w in (o + e).upper() for w in ("WARN", "ALERT"))
    c, o, e = run(f2, "add", "20", "food", "--date", "2026-03-03")
    R["P15_add_alert_at_exactly_100"] = c == 0 and "100%" in (o + e)
    c, o, e = run(f2, "report", "--month", "2026-03")
    R["P16_report_alert_100"] = "100%" in o + e
    # jump straight past 100
    f3 = fresh(); run(f3, "set-budget", "food", "100")
    c, o, e = run(f3, "add", "150", "food", "--date", "2026-03-01")
    R["P17_add_alert_jump_over_100"] = c == 0 and "100%" in (o + e)
    # corrupt file handled
    f4 = fresh(); open(f4, "w").write("{not json")
    c, o, e = run(f4, "report")
    R["P18_corrupt_json_clean_error"] = c != 0 and "Traceback" not in e
    f5 = fresh(); open(f5, "w").write("[]")
    c, o, e = run(f5, "report")
    R["P19_wrong_structure_clean_error"] = c != 0 and "Traceback" not in e
    c, o, e = run(f, "report", "--month", "2026-13")
    R["P20_invalid_month_rejected"] = c != 0 and "Traceback" not in e
    return {k: "pass" if v else "fail" for k, v in R.items()}

res = {s: probes(s) for s in ("A", "B")}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for k in res["A"]: print(f"{k:40} A={res['A'][k]:5} B={res['B'][k]}")
