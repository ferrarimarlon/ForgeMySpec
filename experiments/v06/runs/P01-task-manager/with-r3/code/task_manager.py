#!/usr/bin/env python3
"""CLI task manager backed by SQLite (raw sqlite3, stdlib only)."""
import argparse
import datetime
import os
import sqlite3
import sys

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in-progress", "done")
DEFAULT_DB = "tasks.db"

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


class TaskError(Exception):
    pass


def connect(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def check_choice(value, allowed, name):
    if value not in allowed:
        raise TaskError("invalid %s %r (choose from: %s)" % (name, value, ", ".join(allowed)))
    return value


def check_title(title):
    title = (title or "").strip()
    if not title:
        raise TaskError("title must not be empty")
    return title


def check_due(due):
    if due is None or due == "":
        return None
    try:
        return datetime.date.fromisoformat(due).isoformat()
    except ValueError:
        raise TaskError("invalid due date %r (expected YYYY-MM-DD)" % due)


def add_task(db, title, description="", priority="medium", status="todo", due=None):
    title = check_title(title)
    check_choice(priority, PRIORITIES, "priority")
    check_choice(status, STATUSES, "status")
    due = check_due(due)
    conn = connect(db)
    try:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, priority, status, due_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, description or "", priority, status, due))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_tasks(db, status=None, priority=None):
    if status is not None:
        check_choice(status, STATUSES, "status")
    if priority is not None:
        check_choice(priority, PRIORITIES, "priority")
    sql, params, where = "SELECT * FROM tasks", [], []
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if priority is not None:
        where.append("priority = ?")
        params.append(priority)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def update_task(db, task_id, **fields):
    changes = {}
    if fields.get("title") is not None:
        changes["title"] = check_title(fields["title"])
    if fields.get("description") is not None:
        changes["description"] = fields["description"]
    if fields.get("priority") is not None:
        changes["priority"] = check_choice(fields["priority"], PRIORITIES, "priority")
    if fields.get("status") is not None:
        changes["status"] = check_choice(fields["status"], STATUSES, "status")
    if fields.get("due") is not None:
        changes["due_date"] = check_due(fields["due"])
    conn = connect(db)
    try:
        if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            raise TaskError("task %d not found" % task_id)
        if changes:
            sets = ", ".join("%s = ?" % c for c in changes)
            conn.execute("UPDATE tasks SET %s WHERE id = ?" % sets,
                         (*changes.values(), task_id))
            conn.commit()
    finally:
        conn.close()


def delete_task(db, task_id):
    conn = connect(db)
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise TaskError("task %d not found" % task_id)
    finally:
        conn.close()


COLUMNS = (("ID", "id"), ("Title", "title"), ("Priority", "priority"),
           ("Status", "status"), ("Due", "due_date"))


def format_table(tasks):
    cells = [[str(t[key]) if t[key] is not None else "-" for _, key in COLUMNS]
             for t in tasks]
    headers = [h for h, _ in COLUMNS]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]

    def line(row):
        return " | ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip()

    sep = "-+-".join("-" * w for w in widths)
    return "\n".join([line(headers), sep] + [line(r) for r in cells])


def build_parser():
    p = argparse.ArgumentParser(prog="task_manager.py", description="Simple task manager")
    p.add_argument("--db", default=os.environ.get("TASK_DB", DEFAULT_DB),
                   help="SQLite file (default: $TASK_DB or %s)" % DEFAULT_DB)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title")
    a.add_argument("-d", "--description", default="")
    a.add_argument("-p", "--priority", default="medium")
    a.add_argument("-s", "--status", default="todo")
    a.add_argument("--due", help="due date, YYYY-MM-DD")

    ls = sub.add_parser("list", help="list tasks")
    ls.add_argument("-s", "--status")
    ls.add_argument("-p", "--priority")

    u = sub.add_parser("update", help="update a task")
    u.add_argument("id", type=int)
    u.add_argument("--title")
    u.add_argument("-d", "--description")
    u.add_argument("-p", "--priority")
    u.add_argument("-s", "--status")
    u.add_argument("--due", help="due date, YYYY-MM-DD")

    d = sub.add_parser("delete", help="delete a task")
    d.add_argument("id", type=int)

    dn = sub.add_parser("done", help="mark a task as done")
    dn.add_argument("id", type=int)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "add":
            tid = add_task(args.db, args.title, args.description, args.priority,
                           args.status, args.due)
            print("Added task %d" % tid)
        elif args.command == "list":
            print(format_table(list_tasks(args.db, args.status, args.priority)))
        elif args.command == "update":
            update_task(args.db, args.id, title=args.title, description=args.description,
                        priority=args.priority, status=args.status, due=args.due)
            print("Updated task %d" % args.id)
        elif args.command == "delete":
            delete_task(args.db, args.id)
            print("Deleted task %d" % args.id)
        elif args.command == "done":
            update_task(args.db, args.id, status="done")
            print("Task %d marked as done" % args.id)
    except (TaskError, sqlite3.Error) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
