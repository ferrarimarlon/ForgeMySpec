#!/usr/bin/env python3
"""CLI Task Manager backed by SQLite (stdlib only)."""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.environ.get("TASK_DB", os.path.join(os.path.expanduser("~"), ".tasks.db"))
PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in-progress", "done")
COLUMNS = ("id", "title", "description", "priority", "status", "due_date")


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low','medium','high')),
            status TEXT NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo','in-progress','done')),
            due_date TEXT
        )"""
    )
    return conn


def valid_date(value):
    if value in ("", "none"):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date '{value}', expected YYYY-MM-DD")


def render_table(rows):
    if not rows:
        print("No tasks found.")
        return
    data = [[("" if r[c] is None else str(r[c])).replace("\n", " ") for c in COLUMNS] for r in rows]
    caps = {"title": 30, "description": 40}
    for row in data:
        for i, c in enumerate(COLUMNS):
            cap = caps.get(c)
            if cap and len(row[i]) > cap:
                row[i] = row[i][: cap - 1] + "…"
    headers = [c.upper().replace("_", " ") for c in COLUMNS]
    widths = [max(len(h), *(len(r[i]) for r in data)) for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    fmt = lambda cells: "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"
    print(sep)
    print(fmt(headers))
    print(sep)
    for row in data:
        print(fmt(row))
    print(sep)
    print(f"{len(data)} task(s)")


def cmd_add(conn, a):
    cur = conn.execute(
        "INSERT INTO tasks (title, description, priority, status, due_date) VALUES (?,?,?,?,?)",
        (a.title, a.description, a.priority, a.status, a.due),
    )
    conn.commit()
    print(f"Added task {cur.lastrowid}.")
    return 0


def cmd_list(conn, a):
    sql, params, where = "SELECT * FROM tasks", [], []
    if a.status:
        where.append("status = ?")
        params.append(a.status)
    if a.priority:
        where.append("priority = ?")
        params.append(a.priority)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (
        " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,"
        " due_date IS NULL, due_date, id"
    )
    render_table(conn.execute(sql, params).fetchall())
    return 0


def cmd_update(conn, a):
    fields = {
        "title": a.title,
        "description": a.description,
        "priority": a.priority,
        "status": a.status,
        "due_date": a.due,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    if a.clear_due:
        fields["due_date"] = None
    if not fields:
        print("Nothing to update.", file=sys.stderr)
        return 1
    sets = ", ".join(f"{k} = ?" for k in fields)
    cur = conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", (*fields.values(), a.id))
    conn.commit()
    if cur.rowcount == 0:
        print(f"Task {a.id} not found.", file=sys.stderr)
        return 1
    print(f"Updated task {a.id}.")
    return 0


def cmd_done(conn, a):
    cur = conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (a.id,))
    conn.commit()
    if cur.rowcount == 0:
        print(f"Task {a.id} not found.", file=sys.stderr)
        return 1
    print(f"Task {a.id} marked as done.")
    return 0


def cmd_delete(conn, a):
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (a.id,))
    conn.commit()
    if cur.rowcount == 0:
        print(f"Task {a.id} not found.", file=sys.stderr)
        return 1
    print(f"Deleted task {a.id}.")
    return 0


def cmd_show(conn, a):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (a.id,)).fetchone()
    if row is None:
        print(f"Task {a.id} not found.", file=sys.stderr)
        return 1
    for c in COLUMNS:
        print(f"{c:12}: {'' if row[c] is None else row[c]}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Simple SQLite-backed task manager.")
    p.add_argument("--db", help=f"database path (default: {DB_PATH}, or $TASK_DB)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("add", help="add a task")
    s.add_argument("title")
    s.add_argument("-d", "--description", default="")
    s.add_argument("-p", "--priority", choices=PRIORITIES, default="medium")
    s.add_argument("-s", "--status", choices=STATUSES, default="todo")
    s.add_argument("--due", type=valid_date, help="due date YYYY-MM-DD")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("list", help="list tasks")
    s.add_argument("-s", "--status", choices=STATUSES)
    s.add_argument("-p", "--priority", choices=PRIORITIES)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one task")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("update", help="update a task")
    s.add_argument("id", type=int)
    s.add_argument("-t", "--title")
    s.add_argument("-d", "--description")
    s.add_argument("-p", "--priority", choices=PRIORITIES)
    s.add_argument("-s", "--status", choices=STATUSES)
    s.add_argument("--due", type=valid_date, help="due date YYYY-MM-DD")
    s.add_argument("--clear-due", action="store_true", help="remove the due date")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("done", help="mark a task as done")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_done)

    s = sub.add_parser("delete", help="delete a task")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_delete)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    conn = connect(args.db)
    try:
        return args.func(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
