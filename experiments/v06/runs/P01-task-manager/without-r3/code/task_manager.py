#!/usr/bin/env python3
"""CLI Task Manager backed by SQLite (stdlib only)."""

import argparse
import os
import sqlite3
import sys
from datetime import date, datetime

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in-progress", "done")
DB_PATH = os.environ.get("TASK_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority    TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
    status      TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','in-progress','done')),
    due_date    TEXT
)
"""

COLUMNS = ("id", "title", "description", "priority", "status", "due_date")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def valid_date(value):
    if value == "":
        return None  # allows clearing the due date on update
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date '{value}', expected YYYY-MM-DD")


def nonempty(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("title cannot be empty")
    return value.strip()


def render_table(rows):
    if not rows:
        print("No tasks found.")
        return
    headers = ["ID", "Title", "Description", "Priority", "Status", "Due"]
    data = []
    for r in rows:
        desc = " ".join((r["description"] or "").split())
        if len(desc) > 40:
            desc = desc[:37] + "..."
        title = " ".join(r["title"].split())
        if len(title) > 40:
            title = title[:37] + "..."
        data.append([str(r["id"]), title, desc, r["priority"], r["status"], r["due_date"] or "-"])
    widths = [max(len(h), *(len(row[i]) for row in data)) for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    fmt = lambda cells: "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"
    print(sep)
    print(fmt(headers))
    print(sep)
    for row in data:
        print(fmt(row))
    print(sep)
    print(f"{len(data)} task(s)")


def cmd_add(args):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, priority, status, due_date) VALUES (?, ?, ?, ?, ?)",
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
    query += " ORDER BY id"
    conn = connect()
    try:
        render_table(conn.execute(query, params).fetchall())
    finally:
        conn.close()


def cmd_show(args):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (args.id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return fail(f"Task {args.id} not found.")
    for col in COLUMNS:
        print(f"{col:<12}: {row[col] if row[col] is not None else '-'}")


def cmd_update(args):
    fields = {
        "title": args.title,
        "description": args.description,
        "priority": args.priority,
        "status": args.status,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    if hasattr(args, "due"):  # present (possibly None) only if --due was given
        fields["due_date"] = args.due
    if not fields:
        return fail("Nothing to update. Provide at least one of --title/--description/--priority/--status/--due.")
    sets = ", ".join(f"{k} = ?" for k in fields)
    with connect() as conn:
        cur = conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", (*fields.values(), args.id))
    if cur.rowcount == 0:
        return fail(f"Task {args.id} not found.")
    print(f"Updated task {args.id}.")


def cmd_done(args):
    with connect() as conn:
        cur = conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (args.id,))
    if cur.rowcount == 0:
        return fail(f"Task {args.id} not found.")
    print(f"Task {args.id} marked as done.")


def cmd_delete(args):
    with connect() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (args.id,))
    if cur.rowcount == 0:
        return fail(f"Task {args.id} not found.")
    print(f"Deleted task {args.id}.")


def fail(msg):
    print(msg, file=sys.stderr)
    return 1


def build_parser():
    p = argparse.ArgumentParser(description="Simple CLI task manager (SQLite).")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title", type=nonempty)
    a.add_argument("-d", "--description", default="")
    a.add_argument("-p", "--priority", choices=PRIORITIES, default="medium")
    a.add_argument("-s", "--status", choices=STATUSES, default="todo")
    a.add_argument("--due", type=valid_date, help="due date YYYY-MM-DD")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="list tasks")
    l.add_argument("-s", "--status", choices=STATUSES)
    l.add_argument("-p", "--priority", choices=PRIORITIES)
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one task")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_show)

    u = sub.add_parser("update", help="update a task (empty --due '' clears the date)")
    u.add_argument("id", type=int)
    u.add_argument("--title", type=nonempty)
    u.add_argument("-d", "--description")
    u.add_argument("-p", "--priority", choices=PRIORITIES)
    u.add_argument("-s", "--status", choices=STATUSES)
    u.add_argument("--due", type=valid_date, default=argparse.SUPPRESS)
    u.set_defaults(func=cmd_update)

    dn = sub.add_parser("done", help="mark a task as done")
    dn.add_argument("id", type=int)
    dn.set_defaults(func=cmd_done)

    de = sub.add_parser("delete", help="delete a task")
    de.add_argument("id", type=int)
    de.set_defaults(func=cmd_delete)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
