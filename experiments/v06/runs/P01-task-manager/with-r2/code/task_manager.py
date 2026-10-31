#!/usr/bin/env python3
"""CLI Task Manager: CRUD over tasks stored in SQLite (raw sqlite3, stdlib only)."""
import argparse
import datetime
import os
import sqlite3
import sys

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in-progress", "done")
COLUMNS = (("ID", "id"), ("TITLE", "title"), ("PRIORITY", "priority"),
           ("STATUS", "status"), ("DUE", "due_date"))


class TaskError(Exception):
    pass


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " title TEXT NOT NULL,"
        " description TEXT NOT NULL DEFAULT '',"
        " priority TEXT NOT NULL DEFAULT 'medium'"
        "   CHECK (priority IN ('low','medium','high')),"
        " status TEXT NOT NULL DEFAULT 'todo'"
        "   CHECK (status IN ('todo','in-progress','done')),"
        " due_date TEXT)"
    )
    return conn


def check_title(title):
    if title is None or not title.strip():
        raise TaskError("title must not be empty")
    return title.strip()


def check_choice(name, value, allowed):
    if value not in allowed:
        raise TaskError("invalid %s %r (choose from %s)" % (name, value, ", ".join(allowed)))
    return value


def check_due(value):
    if value in (None, ""):
        return None
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise TaskError("invalid due date %r (use YYYY-MM-DD)" % value)
    if len(value) != 10:
        raise TaskError("invalid due date %r (use YYYY-MM-DD)" % value)
    return value


def get_task(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskError("no task with id %d" % task_id)
    return row


def add_task(conn, title, description="", priority="medium", status="todo", due_date=None):
    title = check_title(title)
    check_choice("priority", priority, PRIORITIES)
    check_choice("status", status, STATUSES)
    due_date = check_due(due_date)
    cur = conn.execute(
        "INSERT INTO tasks (title, description, priority, status, due_date) VALUES (?, ?, ?, ?, ?)",
        (title, description or "", priority, status, due_date),
    )
    conn.commit()
    return cur.lastrowid


def list_tasks(conn, status=None, priority=None):
    sql, params, where = "SELECT * FROM tasks", [], []
    if status is not None:
        where.append("status = ?")
        params.append(check_choice("status", status, STATUSES))
    if priority is not None:
        where.append("priority = ?")
        params.append(check_choice("priority", priority, PRIORITIES))
    if where:
        sql += " WHERE " + " AND ".join(where)
    return conn.execute(sql + " ORDER BY id", params).fetchall()


def update_task(conn, task_id, title=None, description=None, priority=None,
                status=None, due_date=None):
    get_task(conn, task_id)
    fields = {}
    if title is not None:
        fields["title"] = check_title(title)
    if description is not None:
        fields["description"] = description
    if priority is not None:
        fields["priority"] = check_choice("priority", priority, PRIORITIES)
    if status is not None:
        fields["status"] = check_choice("status", status, STATUSES)
    if due_date is not None:
        fields["due_date"] = check_due(due_date)  # "" clears the date
    if not fields:
        raise TaskError("nothing to update")
    # column names come from the fixed set above, values are parameterized
    assignments = ", ".join("%s = ?" % k for k in fields)
    conn.execute("UPDATE tasks SET " + assignments + " WHERE id = ?",
                 list(fields.values()) + [task_id])
    conn.commit()


def delete_task(conn, task_id):
    get_task(conn, task_id)
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


def format_table(rows):
    cells = [[str(r[key]) if r[key] is not None else "-" for _, key in COLUMNS] for r in rows]
    headers = [h for h, _ in COLUMNS]
    widths = [max(len(headers[i]), *(len(c[i]) for c in cells)) if cells else len(headers[i])
              for i in range(len(headers))]
    line = lambda vals: "  ".join(v.ljust(w) for v, w in zip(vals, widths)).rstrip()
    out = [line(headers), "  ".join("-" * w for w in widths)]
    out.extend(line(c) for c in cells)
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(prog="task_manager.py", description="Simple task manager")
    p.add_argument("--db", default=os.environ.get("TASK_DB", "tasks.db"),
                   help="SQLite file (default: $TASK_DB or tasks.db)")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title")
    a.add_argument("-d", "--description", default="")
    a.add_argument("-p", "--priority", default="medium")
    a.add_argument("-s", "--status", default="todo")
    a.add_argument("--due", default=None, help="YYYY-MM-DD")

    l = sub.add_parser("list", help="list tasks")
    l.add_argument("--status")
    l.add_argument("--priority")

    u = sub.add_parser("update", help="update a task")
    u.add_argument("id", type=int)
    u.add_argument("--title")
    u.add_argument("-d", "--description")
    u.add_argument("-p", "--priority")
    u.add_argument("-s", "--status")
    u.add_argument("--due", help="YYYY-MM-DD, or '' to clear")

    x = sub.add_parser("delete", help="delete a task")
    x.add_argument("id", type=int)

    n = sub.add_parser("done", help="mark a task as done")
    n.add_argument("id", type=int)
    return p


def run(args):
    conn = connect(args.db)
    try:
        if args.command == "add":
            tid = add_task(conn, args.title, args.description, args.priority,
                           args.status, args.due)
            print("Added task %d" % tid)
        elif args.command == "list":
            print(format_table(list_tasks(conn, args.status, args.priority)))
        elif args.command == "update":
            update_task(conn, args.id, args.title, args.description, args.priority,
                        args.status, args.due)
            print("Updated task %d" % args.id)
        elif args.command == "delete":
            delete_task(conn, args.id)
            print("Deleted task %d" % args.id)
        elif args.command == "done":
            get_task(conn, args.id)
            update_task(conn, args.id, status="done")
            print("Task %d marked as done" % args.id)
    finally:
        conn.close()


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (TaskError, sqlite3.Error) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
