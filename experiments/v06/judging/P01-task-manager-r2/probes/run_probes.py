"""Black-box probes. Both sides honour $TASK_DB; invocation is identical."""
import json, os, re, sqlite3, subprocess, sys, tempfile, shutil, ast

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def make_runner(side):
    script = os.path.join(ROOT, side, "task_manager.py")
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "t.db")
    def run(*args):
        env = dict(os.environ, TASK_DB=db)
        p = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, env=env, cwd=tmp)
        return p.returncode, p.stdout, p.stderr
    return run, db, tmp, script

def fresh(side):
    return make_runner(side)

def rows_of(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    r = [dict(x) for x in c.execute("select * from tasks order by id")]; c.close(); return r

def probe(side):
    res = {}
    def rec(pid, ok): res[pid] = "pass" if ok else "fail"

    run, db, tmp, script = fresh(side)
    rc, out, _ = run("add", "Buy milk")
    rc2, lout, _ = run("list")
    rec("P01_add_and_list", rc == 0 and rc2 == 0 and "Buy milk" in lout)

    rc, _, _ = run("add", "Write report", "--description", "quarterly", "--priority", "high", "--status", "in-progress", "--due", "2026-12-01")
    r = rows_of(db)[-1]
    rec("P02_all_fields_stored", rc == 0 and r.get("title") == "Write report" and r.get("description") == "quarterly"
        and r.get("priority") == "high" and r.get("status") == "in-progress" and r.get("due_date") == "2026-12-01")
    _, lout, _ = run("list")
    rec("P03_list_shows_fields", all(s in lout for s in ["Write report", "high", "in-progress", "2026-12-01"]))
    rec("P04_list_shows_description", "quarterly" in lout)
    cols = None
    try:
        c = sqlite3.connect(db); cols = {x[1] for x in c.execute("pragma table_info(tasks)")}; c.close()
    except Exception: pass
    rec("P05_schema_columns", cols is not None and {"id","title","description","priority","status","due_date"} <= cols)
    # table format: header line containing ID and Title, separator line, columns aligned
    lines = [l for l in lout.splitlines() if l.strip()]
    hdr = [l for l in lines if re.search(r"\bID\b", l, re.I) and re.search(r"title", l, re.I)]
    sep = [l for l in lines if re.fullmatch(r"[\s\-+=|]+", l)]
    rows = [l for l in lines if "Buy milk" in l or "Write report" in l]
    aligned = False
    if hdr and len(rows) == 2:
        # column of priority value starts at same offset in both rows, or rows have equal width
        aligned = rows[0].find("medium") == rows[1].find("high") or len(rows[0].rstrip()) == len(rows[1].rstrip())
    rec("P06_table_format", bool(hdr) and bool(sep) and aligned)

    # update
    rc, _, _ = run("update", "1", "--title", "Buy oat milk", "--priority", "low", "--status", "in-progress")
    r = rows_of(db)[0]
    rec("P07_update_fields", rc == 0 and r["title"] == "Buy oat milk" and r["priority"] == "low" and r["status"] == "in-progress")
    rc, _, _ = run("update", "1", "--due", "2027-01-15", "--description", "2 litres")
    r = rows_of(db)[0]
    rec("P08_update_due_desc", rc == 0 and r["due_date"] == "2027-01-15" and r["description"] == "2 litres")
    rc, _, err = run("update", "999", "--title", "x")
    rec("P09_update_missing_id_errors", rc != 0 and err.strip() != "")

    # filters
    run("add", "Low todo", "--priority", "low", "--status", "todo")
    run("add", "High done", "--priority", "high", "--status", "done")
    _, o, _ = run("list", "--status", "todo")
    rec("P10_filter_status", "Low todo" in o and "High done" not in o and "Write report" not in o)
    _, o, _ = run("list", "--priority", "high")
    rec("P11_filter_priority", "High done" in o and "Write report" in o and "Low todo" not in o and "Buy oat milk" not in o)
    _, o, _ = run("list", "--status", "in-progress", "--priority", "low")
    rec("P12_filter_combined", "Buy oat milk" in o and "Write report" not in o and "Low todo" not in o)

    # done
    rc, _, _ = run("done", "3")
    rec("P13_mark_done", rc == 0 and rows_of(db)[2]["status"] == "done")
    rc, _, err = run("done", "999")
    rec("P14_done_missing_id_errors", rc != 0 and err.strip() != "")

    # validation
    n = len(rows_of(db))
    rc, _, _ = run("add", "Bad", "--priority", "urgent")
    rec("P15_reject_bad_priority", rc != 0 and len(rows_of(db)) == n)
    rc, _, _ = run("add", "Bad", "--status", "blocked")
    rec("P16_reject_bad_status", rc != 0 and len(rows_of(db)) == n)
    rc, _, _ = run("add", "Bad", "--due", "2026-13-45")
    rec("P17_reject_bad_date", rc != 0 and len(rows_of(db)) == n)
    rc, _, _ = run("update", "1", "--status", "blocked")
    rec("P18_update_reject_bad_status", rc != 0 and rows_of(db)[0]["status"] == "in-progress")

    # delete
    rc, _, _ = run("delete", "2")
    _, o, _ = run("list")
    rec("P19_delete", rc == 0 and "Write report" not in o and all(r["id"] != 2 for r in rows_of(db)))
    rc, _, err = run("delete", "999")
    rec("P20_delete_missing_id_errors", rc != 0 and err.strip() != "")

    # injection-like literal
    t = "x'); DROP TABLE tasks;--"
    rc, _, _ = run("add", t)
    rec("P21_sql_literal_safe", rc == 0 and rows_of(db)[-1]["title"] == t)

    # persistence across process with a new db path
    run2, db2, tmp2, _ = fresh(side)
    run2("add", "Persist me")
    _, o, _ = run2("list")
    rec("P22_persisted_in_sqlite_file", os.path.exists(db2) and "Persist me" in o and rows_of(db2)[0]["title"] == "Persist me")
    _, o, _ = run2("list", "--status", "done")
    rec("P23_empty_filter_no_crash", True if "Traceback" not in o else False)

    # static: stdlib only, sqlite3 used, single entry file
    src = open(script).read()
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): mods |= {a.name.split(".")[0] for a in node.names}
        if isinstance(node, ast.ImportFrom) and node.module: mods.add(node.module.split(".")[0])
    rec("P24_stdlib_only", all(m in sys.stdlib_module_names for m in mods))
    rec("P25_raw_sqlite3", "sqlite3" in mods and not ({"sqlalchemy","peewee","pony","django"} & mods))
    rc, out, err = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True, cwd=tmp).returncode, None, None
    rec("P26_entry_point_help", rc == 0)
    for d in (tmp, tmp2): shutil.rmtree(d, ignore_errors=True)
    return res

if __name__ == "__main__":
    out = {s: probe(s) for s in ("A", "B")}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1)
    for s in out:
        print(s, sum(v == "pass" for v in out[s].values()), "/", len(out[s]), [k for k, v in out[s].items() if v == "fail"])
