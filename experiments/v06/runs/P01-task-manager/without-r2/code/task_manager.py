#!/usr/bin/env python3
"""CLI Task Manager backed by SQLite (stdlib only).

Usage:
    task_manager.py add "Title" [-d DESC] [-p low|medium|high] [-s STATUS] [--due YYYY-MM-DD]
    task_manager.py list [-s STATUS] [-p PRIORITY]
    task_manager.py show ID
    task_manager.py update ID [--title T] [-d DESC] [-p P] [-s S] [--due DATE]
    task_manager.py done ID
    task_manager.py delete ID

Database path: $TASK_DB, or tasks.db next to this script.
"""
import argparse
import os
import sqlite3
import sys
from datetime import date

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in-progress", "done")
DB_PATH = os.environ.get(
    "TASK_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high')),
    status      TEXT NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in-progress', 'done')),
    due_date    TEXT
)
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def valid_date(value):
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date '{value}' (use YYYY-MM-DD)")


def render_table(rows):
    headers = ["ID", "Title", "Description", "Priority", "Status", "Due"]
    data = [
        [str(r["id"]), r["title"], r["description"].replace("\n", " "),
         r["priority"], r["status"], r["due_date"] or "-"]
        for r in rows
    ]
    # Cap long free-text columns so the table stays readable.
    caps = {1: 30, 2: 40}
    for row in data:
        for i, cap in caps.items():
            if len(row[i]) > cap:
                row[i] = row[i][: cap - 1] + "…"
    widths = [max(len(h), *(len(r[i]) for r in data)) for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def line(cells):
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    return "\n".join([sep, line(headers), sep, *(line(r) for r in data), sep])


def get_task(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        sys.exit(f"Error: task {task_id} not found.")
    return row


def cmd_add(args):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, priority, status, due_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (args.title, args.description, args.priority, args.status, args.due),
        )
    print(f"Added task {cur.lastrowid}.")


def cmd_list(args):
    query, params = "SELECT * FROM tasks", []
    clauses = []
    if args.status:
        clauses.append("status = ?")
        params.append(args.status)
    if args.priority:
        clauses.append("priority = ?")
        params.append(args.priority)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += (
        " ORDER BY due_date IS NULL, due_date, "
        "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id"
    )
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    if not rows:
        print("No tasks found.")
        return
    print(render_table(rows))
    print(f"{len(rows)} task(s)")


def cmd_show(args):
    with connect() as conn:
        t = get_task(conn, args.id)
    for key in t.keys():
        print(f"{key:>12}: {t[key] if t[key] is not None else '-'}")


def cmd_update(args):
    fields = {
        "title": args.title,
        "description": args.description,
        "priority": args.priority,
        "status": args.status,
        "due_date": args.due,
    }
    if args.clear_due:
        fields["due_date"] = None
    changes = {k: v for k, v in fields.items() if v is not None or (k == "due_date" and args.clear_due)}
    if not changes:
        sys.exit("Error: nothing to update; pass at least one field.")
    with connect() as conn:
        get_task(conn, args.id)
        sets = ", ".join(f"{k} = ?" for k in changes)  # keys are fixed above, not user input
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", (*changes.values(), args.id))
    print(f"Updated task {args.id}.")


def cmd_done(args):
    with connect() as conn:
        get_task(conn, args.id)
        conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (args.id,))
    print(f"Task {args.id} marked as done.")


def cmd_delete(args):
    with connect() as conn:
        get_task(conn, args.id)
        conn.execute("DELETE FROM tasks WHERE id = ?", (args.id,))
    print(f"Deleted task {args.id}.")


def build_parser():
    p = argparse.ArgumentParser(description="Simple SQLite-backed task manager.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title")
    a.add_argument("-d", "--description", default="")
    a.add_argument("-p", "--priority", choices=PRIORITIES, default="medium")
    a.add_argument("-s", "--status", choices=STATUSES, default="todo")
    a.add_argument("--due", type=valid_date, help="due date, YYYY-MM-DD")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="list tasks")
    l.add_argument("-s", "--status", choices=STATUSES)
    l.add_argument("-p", "--priority", choices=PRIORITIES)
    l.set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="show one task in full")
    sh.add_argument("id", type=int)
    sh.set_defaults(func=cmd_show)

    u = sub.add_parser("update", help="update task fields")
    u.add_argument("id", type=int)
    u.add_argument("--title")
    u.add_argument("-d", "--description")
    u.add_argument("-p", "--priority", choices=PRIORITIES)
    u.add_argument("-s", "--status", choices=STATUSES)
    u.add_argument("--due", type=valid_date, help="due date, YYYY-MM-DD")
    u.add_argument("--clear-due", action="store_true", help="remove the due date")
    u.set_defaults(func=cmd_update)

    dn = sub.add_parser("done", help="mark a task as done")
    dn.add_argument("id", type=int)
    dn.set_defaults(func=cmd_done)

    de = sub.add_parser("delete", help="delete a task")
    de.add_argument("id", type=int)
    de.set_defaults(func=cmd_delete)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
