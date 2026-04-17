import sqlite3
import argparse
import sys
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")


def init():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, priority TEXT,
        status TEXT DEFAULT 'todo', due_date TEXT)""")
    con.commit()
    return con


def add_task(con, title, desc, priority, status, due):
    cur = con.execute(
        "INSERT INTO tasks(title,description,priority,status,due_date) VALUES(?,?,?,?,?)",
        (title, desc, priority, status, due))
    con.commit()
    return cur.lastrowid


def list_tasks(con, status=None, priority=None):
    q = "SELECT * FROM tasks"
    params = []
    where = []
    if status:
        where.append("status=?"); params.append(status)
    if priority:
        where.append("priority=?"); params.append(priority)
    if where:
        q += " WHERE " + " AND ".join(where)
    return con.execute(q, params).fetchall()


def print_tasks(rows):
    if not rows:
        print("No tasks.")
        return
    print(f"{'ID':<4}  {'Title':<30}  {'Priority':<8}  {'Status':<11}  {'Due':<12}")
    print("-" * 73)
    for r in rows:
        due = r[5] if r[5] else "-"
        print(f"{r[0]:<4}  {str(r[1])[:30]:<30}  {r[3]:<8}  {r[4]:<11}  {due:<12}")


def update_task(con, tid, **kw):
    if not kw:
        return 0
    q = "UPDATE tasks SET " + ",".join(f"{k}=?" for k in kw) + " WHERE id=?"
    cur = con.execute(q, list(kw.values()) + [tid])
    con.commit()
    return cur.rowcount


def delete_task(con, tid):
    cur = con.execute("DELETE FROM tasks WHERE id=?", (tid,))
    con.commit()
    return cur.rowcount


def main():
    con = init()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    pa = sub.add_parser("add")
    pa.add_argument("--title", required=True)
    pa.add_argument("--description", default="")
    pa.add_argument("--priority", default="medium")
    pa.add_argument("--status", default="todo")
    pa.add_argument("--due-date", dest="due_date", default="")

    pl = sub.add_parser("list")
    pl.add_argument("--status", default=None)
    pl.add_argument("--priority", default=None)

    pu = sub.add_parser("update")
    pu.add_argument("id", type=int)
    pu.add_argument("--title", default=None)
    pu.add_argument("--description", default=None)
    pu.add_argument("--priority", default=None)
    pu.add_argument("--status", default=None)
    pu.add_argument("--due-date", dest="due_date", default=None)

    pd = sub.add_parser("done")
    pd.add_argument("id", type=int)

    pdel = sub.add_parser("delete")
    pdel.add_argument("id", type=int)

    args = p.parse_args()

    if args.cmd == "add":
        tid = add_task(con, args.title, args.description, args.priority, args.status, args.due_date)
        print(f"Added task {tid}: {args.title}")

    elif args.cmd == "list":
        rows = list_tasks(con, args.status, args.priority)
        print_tasks(rows)

    elif args.cmd == "update":
        kw = {}
        if args.title: kw["title"] = args.title
        if args.description: kw["description"] = args.description
        if args.priority: kw["priority"] = args.priority
        if args.status: kw["status"] = args.status
        if args.due_date: kw["due_date"] = args.due_date
        n = update_task(con, args.id, **kw)
        if n == 0:
            print(f"Task {args.id} not found"); sys.exit(1)
        print(f"Task {args.id} updated")

    elif args.cmd == "done":
        n = update_task(con, args.id, status="done")
        if n == 0:
            print(f"Task {args.id} not found"); sys.exit(1)
        print(f"Task {args.id} done")

    elif args.cmd == "delete":
        n = delete_task(con, args.id)
        if n == 0:
            print(f"Task {args.id} not found"); sys.exit(1)
        print(f"Task {args.id} deleted")

    else:
        p.print_help()


if __name__ == "__main__":
    main()
