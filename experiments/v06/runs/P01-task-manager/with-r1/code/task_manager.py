#!/usr/bin/env python3
"""Task manager CLI: CRUD on tasks stored in SQLite (raw sqlite3, stdlib only)."""
import argparse
import datetime
import sqlite3
import sys

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in-progress", "done")
COLUMNS = ("id", "title", "description", "priority", "status", "due_date")
DEFAULT_DB = "tasks.db"


class TaskError(Exception):
    """Invalid input or unknown task; reported on stderr with exit code 1."""


def connect(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high')),
            status TEXT NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in-progress', 'done')),
            due_date TEXT
        )"""
    )
    conn.commit()
    return conn


def _check_choice(name, value, allowed):
    if value is not None and value not in allowed:
        raise TaskError("invalid %s %r (allowed: %s)" % (name, value, ", ".join(allowed)))


def _check_due(value):
    if value in (None, ""):
        return None
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise TaskError("invalid due date %r (expected YYYY-MM-DD)" % value)
    return value


def _check_title(value):
    if value is not None and not value.strip():
        raise TaskError("title must not be empty")


def add_task(conn, title, description="", priority="medium", status="todo", due_date=None):
    _check_title(title)
    _check_choice("priority", priority, PRIORITIES)
    _check_choice("status", status, STATUSES)
    due_date = _check_due(due_date)
    cur = conn.execute(
        "INSERT INTO tasks (title, description, priority, status, due_date) VALUES (?, ?, ?, ?, ?)",
        (title, description, priority, status, due_date),
    )
    conn.commit()
    return cur.lastrowid


def list_tasks(conn, status=None, priority=None):
    _check_choice("status", status, STATUSES)
    _check_choice("priority", priority, PRIORITIES)
    sql = "SELECT id, title, description, priority, status, due_date FROM tasks"
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    return conn.execute(sql, params).fetchall()


def update_task(conn, task_id, **fields):
    changes = {k: v for k, v in fields.items() if v is not None}
    if "title" in changes:
        _check_title(changes["title"])
    _check_choice("priority", changes.get("priority"), PRIORITIES)
    _check_choice("status", changes.get("status"), STATUSES)
    if "due_date" in changes:
        changes["due_date"] = _check_due(changes["due_date"])
    if not changes:
        raise TaskError("nothing to update")
    assignments = ", ".join("%s = ?" % k for k in changes)  # keys are fixed column names
    cur = conn.execute(
        "UPDATE tasks SET %s WHERE id = ?" % assignments, list(changes.values()) + [task_id]
    )
    conn.commit()
    if cur.rowcount == 0:
        raise TaskError("task %d not found" % task_id)


def delete_task(conn, task_id):
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise TaskError("task %d not found" % task_id)


def mark_done(conn, task_id):
    update_task(conn, task_id, status="done")


def format_table(rows):
    headers = [c.upper() for c in COLUMNS]
    cells = [["" if v is None else str(v).replace("\n", " ") for v in row] for row in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]

    def line(values):
        return "| " + " | ".join(v.ljust(w) for v, w in zip(values, widths)) + " |"

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    out = [sep, line(headers), sep]
    out.extend(line(r) for r in cells)
    out.append(sep)
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(prog="task_manager.py", description="Simple task manager")
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite file (default: %s)" % DEFAULT_DB)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title")
    a.add_argument("-d", "--description", default="")
    a.add_argument("-p", "--priority", default="medium")
    a.add_argument("-s", "--status", default="todo")
    a.add_argument("--due", dest="due_date", default=None, help="YYYY-MM-DD")

    ls = sub.add_parser("list", help="list tasks")
    ls.add_argument("--status")
    ls.add_argument("--priority")

    u = sub.add_parser("update", help="update a task")
    u.add_argument("id", type=int)
    u.add_argument("--title")
    u.add_argument("-d", "--description")
    u.add_argument("-p", "--priority")
    u.add_argument("-s", "--status")
    u.add_argument("--due", dest="due_date", help="YYYY-MM-DD")

    de = sub.add_parser("delete", help="delete a task")
    de.add_argument("id", type=int)

    dn = sub.add_parser("done", help="mark a task as done")
    dn.add_argument("id", type=int)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        conn = connect(args.db)
        try:
            if args.command == "add":
                tid = add_task(conn, args.title, args.description, args.priority,
                               args.status, args.due_date)
                print("Added task %d" % tid)
            elif args.command == "list":
                print(format_table(list_tasks(conn, args.status, args.priority)))
            elif args.command == "update":
                update_task(conn, args.id, title=args.title, description=args.description,
                            priority=args.priority, status=args.status, due_date=args.due_date)
                print("Updated task %d" % args.id)
            elif args.command == "delete":
                delete_task(conn, args.id)
                print("Deleted task %d" % args.id)
            elif args.command == "done":
                mark_done(conn, args.id)
                print("Task %d marked as done" % args.id)
        finally:
            conn.close()
    except (TaskError, sqlite3.Error) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
