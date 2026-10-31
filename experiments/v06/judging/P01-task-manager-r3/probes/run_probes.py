import json, os, subprocess, sys, tempfile, sqlite3, re, ast
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def run(side, db, *args):
    env = dict(os.environ, TASK_DB=db)
    p = subprocess.run([sys.executable, os.path.join(ROOT, side, "task_manager.py"), *args],
                       capture_output=True, text=True, env=env, cwd=os.path.dirname(db), timeout=30)
    return p

def fresh():
    d = tempfile.mkdtemp()
    return os.path.join(d, "t.db")

def rows(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    r = [dict(x) for x in c.execute("select * from tasks order by id")]; c.close(); return r

def probes(side):
    res = {}
    def rec(pid, fn):
        try: res[pid] = "pass" if fn() else "fail"
        except Exception as e: res[pid] = "fail"; print(side, pid, "EXC", e)
    def p_add():
        db = fresh(); r = run(side, db, "add", "Buy milk", "-d", "2 liters", "-p", "high", "--due", "2026-12-01")
        rs = rows(db)
        return r.returncode == 0 and len(rs) == 1 and rs[0]["title"] == "Buy milk" and rs[0]["priority"] == "high" and rs[0]["due_date"] == "2026-12-01" and rs[0]["description"] == "2 liters" and rs[0]["status"] == "todo"
    def p_fields():
        db = fresh(); run(side, db, "add", "x")
        return set(["id","title","description","priority","status","due_date"]) <= set(rows(db)[0].keys())
    def p_list():
        db = fresh(); run(side, db, "add", "Alpha"); run(side, db, "add", "Beta")
        r = run(side, db, "list"); return r.returncode == 0 and "Alpha" in r.stdout and "Beta" in r.stdout
    def p_table():
        db = fresh(); run(side, db, "add", "Alpha", "-p", "low", "--due", "2026-01-02")
        out = run(side, db, "list").stdout
        hdr = any(all(h.lower() in l.lower() for h in ("id","title","priority","status")) for l in out.splitlines())
        sep = any(re.fullmatch(r"[\s\-+|=]{5,}", l) for l in out.splitlines())
        return hdr and sep and "2026-01-02" in out
    def p_desc_visible():
        db = fresh(); run(side, db, "add", "Alpha", "-d", "zebradesc")
        return "zebradesc" in run(side, db, "list").stdout
    def p_update():
        db = fresh(); run(side, db, "add", "Alpha")
        r = run(side, db, "update", "1", "--title", "Gamma", "-p", "high", "-s", "in-progress", "-d", "nd", "--due", "2027-03-04")
        x = rows(db)[0]
        return r.returncode == 0 and x["title"] == "Gamma" and x["priority"] == "high" and x["status"] == "in-progress" and x["description"] == "nd" and x["due_date"] == "2027-03-04"
    def p_update_partial():
        db = fresh(); run(side, db, "add", "Alpha", "-p", "low", "-d", "keep")
        run(side, db, "update", "1", "-s", "done"); x = rows(db)[0]
        return x["title"] == "Alpha" and x["priority"] == "low" and x["description"] == "keep" and x["status"] == "done"
    def p_update_missing():
        db = fresh(); run(side, db, "add", "Alpha"); r = run(side, db, "update", "99", "--title", "Z")
        return r.returncode != 0 and "Traceback" not in r.stderr
    def p_delete():
        db = fresh(); run(side, db, "add", "Alpha"); run(side, db, "add", "Beta")
        r = run(side, db, "delete", "1"); rs = rows(db)
        return r.returncode == 0 and len(rs) == 1 and rs[0]["title"] == "Beta"
    def p_delete_missing():
        db = fresh(); run(side, db, "add", "Alpha"); r = run(side, db, "delete", "42")
        return r.returncode != 0 and "Traceback" not in r.stderr and len(rows(db)) == 1
    def p_bad_priority():
        db = fresh(); r = run(side, db, "add", "A", "-p", "urgent")
        ok = r.returncode != 0 and "Traceback" not in r.stderr
        return ok and (not os.path.exists(db) or len(rows(db)) == 0)
    def p_bad_status():
        db = fresh(); r = run(side, db, "add", "A", "-s", "blocked")
        run(side, db, "add", "B"); r2 = run(side, db, "update", "1", "-s", "blocked")
        return r.returncode != 0 and r2.returncode != 0 and "Traceback" not in r.stderr + r2.stderr and rows(db)[0]["status"] == "todo"
    def p_bad_date():
        db = fresh(); r = run(side, db, "add", "A", "--due", "2026-13-45")
        r2 = run(side, db, "add", "A", "--due", "tomorrow")
        return r.returncode != 0 and r2.returncode != 0 and "Traceback" not in r.stderr + r2.stderr
    def p_persist():
        db = fresh(); run(side, db, "add", "Persisted")
        return "Persisted" in run(side, db, "list").stdout and os.path.getsize(db) > 0
    def p_filter_status():
        db = fresh(); run(side, db, "add", "TodoOne"); run(side, db, "add", "ProgOne", "-s", "in-progress"); run(side, db, "add", "DoneOne", "-s", "done")
        o = run(side, db, "list", "-s", "in-progress").stdout
        return "ProgOne" in o and "TodoOne" not in o and "DoneOne" not in o
    def p_filter_priority():
        db = fresh(); run(side, db, "add", "LowOne", "-p", "low"); run(side, db, "add", "HighOne", "-p", "high")
        o = run(side, db, "list", "-p", "high").stdout
        return "HighOne" in o and "LowOne" not in o
    def p_filter_both():
        db = fresh(); run(side, db, "add", "HT", "-p", "high"); run(side, db, "add", "HD", "-p", "high", "-s", "done"); run(side, db, "add", "LD", "-p", "low", "-s", "done")
        o = run(side, db, "list", "-s", "done", "-p", "high").stdout
        return "HD" in o and "HT" not in o and "LD" not in o
    def p_filter_invalid():
        db = fresh(); run(side, db, "add", "A"); r = run(side, db, "list", "-s", "bogus")
        return r.returncode != 0 and "Traceback" not in r.stderr
    def p_done():
        db = fresh(); run(side, db, "add", "A"); r = run(side, db, "done", "1")
        return r.returncode == 0 and rows(db)[0]["status"] == "done"
    def p_done_missing():
        db = fresh(); r = run(side, db, "done", "7")
        return r.returncode != 0 and "Traceback" not in r.stderr
    def p_empty_title():
        db = fresh(); r = run(side, db, "add", "   ")
        return r.returncode != 0 and (not os.path.exists(db) or len(rows(db)) == 0)
    def p_sqli():
        db = fresh(); run(side, db, "add", "x'); DROP TABLE tasks;--")
        return rows(db)[0]["title"] == "x'); DROP TABLE tasks;--"
    def p_stdlib():
        src = open(os.path.join(ROOT, side, "task_manager.py")).read()
        mods = set()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
        return mods <= {"argparse","os","sqlite3","sys","datetime"}
    def p_no_orm():
        src = open(os.path.join(ROOT, side, "task_manager.py")).read()
        return "import sqlite3" in src and not re.search(r"sqlalchemy|peewee|pony|django", src, re.I)
    def p_entry():
        return os.path.isfile(os.path.join(ROOT, side, "task_manager.py")) and run(side, fresh(), "--help").returncode == 0
    def p_bad_id():
        db = fresh(); r = run(side, db, "delete", "abc")
        return r.returncode != 0 and "Traceback" not in r.stderr
    for k, f in list(locals().items()):
        if k.startswith("p_"): rec(k[2:], f)
    return res

out = {"A": probes("A"), "B": probes("B")}
json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
