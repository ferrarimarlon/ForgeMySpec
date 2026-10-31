"""Black-box probes. Same expectations for A and B; only invocation (--db) adapted."""
import json, os, subprocess, sys, tempfile, re, sqlite3, ast

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(side, db, *args):
    script = os.path.join(ROOT, side, "task_manager.py")
    env = dict(os.environ); env["TASK_DB"] = db
    r = subprocess.run([sys.executable, script, "--db", db, *args], capture_output=True, text=True, env=env, cwd=os.path.dirname(db))
    return r

def probes(side):
    res = {}; log = {}
    def rec(pid, ok, info=""):
        res[pid] = "pass" if ok else "fail"; log[pid] = info
    def fresh():
        d = tempfile.mkdtemp(); return os.path.join(d, "t.db")
    # P01 add + list shows it
    db = fresh()
    r = run(side, db, "add", "Buy milk", "-d", "2 liters", "-p", "high", "--due", "2026-12-01")
    l = run(side, db, "list")
    rec("P01_add_list", r.returncode == 0 and "Buy milk" in l.stdout and "2 liters" in l.stdout and "2026-12-01" in l.stdout and "high" in l.stdout, r.stdout+r.stderr+l.stdout)
    # P02 fields in schema
    cols = [c[1] for c in sqlite3.connect(db).execute("PRAGMA table_info(tasks)")]
    rec("P02_fields", all(c in cols for c in ["id","title","description","priority","status","due_date"]), str(cols))
    # P03 default status todo
    rec("P03_default_status_todo", "todo" in l.stdout, "")
    # P04 persistence across invocations (separate process already); verify via sqlite file
    rows = sqlite3.connect(db).execute("select title from tasks").fetchall()
    rec("P04_persist_sqlite", rows == [("Buy milk",)], str(rows))
    # P05 update
    u = run(side, db, "update", "1", "--title", "Buy oat milk", "-p", "low", "-s", "in-progress")
    row = sqlite3.connect(db).execute("select title,priority,status from tasks where id=1").fetchone()
    rec("P05_update", u.returncode == 0 and row == ("Buy oat milk","low","in-progress"), str(row)+u.stderr)
    # P06 mark done
    d = run(side, db, "done", "1")
    st = sqlite3.connect(db).execute("select status from tasks where id=1").fetchone()
    rec("P06_done", d.returncode == 0 and st == ("done",), str(st))
    # P07 delete
    x = run(side, db, "delete", "1")
    n = sqlite3.connect(db).execute("select count(*) from tasks").fetchone()[0]
    rec("P07_delete", x.returncode == 0 and n == 0, str(n))
    # P08/P09 filters
    db = fresh()
    run(side, db, "add", "AAA_low_todo", "-p", "low")
    run(side, db, "add", "BBB_high_todo", "-p", "high")
    run(side, db, "add", "CCC_high_done", "-p", "high", "-s", "done")
    run(side, db, "add", "DDD_med_prog", "-p", "medium", "-s", "in-progress")
    f = run(side, db, "list", "--status", "done").stdout
    rec("P08_filter_status", "CCC_high_done" in f and "AAA" not in f and "BBB" not in f and "DDD" not in f, f)
    f = run(side, db, "list", "--priority", "high").stdout
    rec("P09_filter_priority", "BBB" in f and "CCC" in f and "AAA" not in f and "DDD" not in f, f)
    f = run(side, db, "list", "--status", "todo", "--priority", "high").stdout
    rec("P10_filter_combined", "BBB" in f and "CCC" not in f and "AAA" not in f, f)
    f = run(side, db, "list", "--status", "in-progress").stdout
    rec("P11_filter_inprogress", "DDD" in f and "AAA" not in f, f)
    # P12 table format: header with all column names + aligned borders
    t = run(side, db, "list").stdout
    lines = [x for x in t.splitlines() if x.startswith(("|","+"))]
    hdr = t.upper()
    ok = all(h in hdr for h in ["ID","TITLE","DESCRIPTION","PRIORITY","STATUS","DUE"]) and len(lines) >= 6 and len({len(x) for x in lines}) == 1
    rec("P12_table", ok, t)
    # P13 invalid priority rejected, nothing stored
    db = fresh()
    r = run(side, db, "add", "X", "-p", "urgent")
    n = sqlite3.connect(db).execute("select count(*) from tasks").fetchone()[0] if os.path.exists(db) else 0
    rec("P13_invalid_priority", r.returncode != 0 and n == 0 and "Traceback" not in r.stderr, r.stderr)
    r = run(side, db, "add", "X", "-s", "blocked")
    n = sqlite3.connect(db).execute("select count(*) from tasks").fetchone()[0] if os.path.exists(db) else 0
    rec("P14_invalid_status", r.returncode != 0 and n == 0 and "Traceback" not in r.stderr, r.stderr)
    r = run(side, db, "add", "X", "--due", "2026-13-45")
    n = sqlite3.connect(db).execute("select count(*) from tasks").fetchone()[0] if os.path.exists(db) else 0
    rec("P15_invalid_due", r.returncode != 0 and n == 0 and "Traceback" not in r.stderr, r.stderr)
    # P16 nonexistent id errors
    outs = [run(side, db, *a) for a in (["update","99","--title","z"],["delete","99"],["done","99"])]
    rec("P16_missing_id", all(o.returncode != 0 and "Traceback" not in o.stderr for o in outs), " ".join(o.stderr for o in outs))
    # P17 invalid filter rejected
    r = run(side, db, "list", "--status", "bogus")
    rec("P17_invalid_filter", r.returncode != 0 and "Traceback" not in r.stderr, r.stderr)
    # P18 empty title rejected
    r = run(side, db, "add", "   ")
    n = sqlite3.connect(db).execute("select count(*) from tasks").fetchone()[0]
    rec("P18_empty_title", r.returncode != 0 and n == 0, r.stdout + r.stderr)
    # P19 SQL injection-ish title stored literally
    db = fresh()
    evil = "x'); DROP TABLE tasks;--"
    run(side, db, "add", evil)
    rows = sqlite3.connect(db).execute("select title from tasks").fetchall()
    rec("P19_sql_literal", rows == [(evil,)], str(rows))
    # P20 update invalid priority rejected without traceback
    r = run(side, db, "update", "1", "-p", "urgent")
    rec("P20_update_invalid", r.returncode != 0 and "Traceback" not in r.stderr, r.stderr)
    # P21 unwritable DB path -> clean error
    r = run(side, "/nonexistent_dir_xyz/t.db", "list") if False else subprocess.run([sys.executable, os.path.join(ROOT, side, "task_manager.py"), "--db", "/nonexistent_dir_xyz/t.db", "list"], capture_output=True, text=True)
    rec("P21_bad_db_path", r.returncode != 0 and "Traceback" not in r.stderr, r.stderr[-300:])
    # P22 stdlib only, raw sqlite3, single file
    src = open(os.path.join(ROOT, side, "task_manager.py")).read()
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import): mods |= {a.name.split(".")[0] for a in node.names}
        if isinstance(node, ast.ImportFrom): mods.add((node.module or "").split(".")[0])
    rec("P22_stdlib_only", mods <= {"argparse","datetime","sqlite3","sys","os"}, str(mods))
    # P23 long title preserved in list output (no silent truncation)
    db = fresh()
    long = "T" * 50 + "END"
    run(side, db, "add", long)
    rec("P23_long_title_shown", long in run(side, db, "list").stdout, "")
    return res, log

if __name__ == "__main__":
    out, logs = {}, {}
    for s in ("A", "B"):
        out[s], logs[s] = probes(s)
    json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
    json.dump(logs, open(os.path.join(ROOT, "probes", "log.json"), "w"), indent=1)
    for s in out:
        print(s, sum(v == "pass" for v in out[s].values()), "/", len(out[s]), [k for k, v in out[s].items() if v == "fail"])
