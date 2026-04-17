import sqlite3
import argparse
import sys
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"todo", "in-progress", "done"}

COL_WIDTHS = {"id": 4, "title": 30, "priority": 8, "status": 11, "due": 12}


# ── DB layer ──────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                description TEXT    NOT NULL DEFAULT '',
                priority    TEXT    NOT NULL DEFAULT 'medium',
                status      TEXT    NOT NULL DEFAULT 'todo',
                due_date    TEXT    NOT NULL DEFAULT ''
            )
        """)


def db_add(title, description, priority, status, due_date):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, priority, status, due_date) VALUES (?,?,?,?,?)",
            (title, description, priority, status, due_date),
        )
        return cur.lastrowid


def db_get(task_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return row


def db_list(status=None, priority=None):
    query = "SELECT * FROM tasks"
    params = []
    conditions = []
    if status:
        conditions.append("status=?")
        params.append(status)
    if priority:
        conditions.append("priority=?")
        params.append(priority)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return rows


def db_update(task_id, **fields):
    if not fields:
        return 0
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [task_id]
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)
        return cur.rowcount


def db_delete(task_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        return cur.rowcount


# ── Table formatter ───────────────────────────────────────────────────────────

def _cell(value, width):
    s = str(value) if value else "-"
    return s[:width].ljust(width)


def print_table(rows):
    if not rows:
        print("No tasks found.")
        return
    header = (
        _cell("ID", COL_WIDTHS["id"]) + "  " +
        _cell("Title", COL_WIDTHS["title"]) + "  " +
        _cell("Priority", COL_WIDTHS["priority"]) + "  " +
        _cell("Status", COL_WIDTHS["status"]) + "  " +
        _cell("Due", COL_WIDTHS["due"])
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for row in rows:
        print(
            _cell(row["id"], COL_WIDTHS["id"]) + "  " +
            _cell(row["title"], COL_WIDTHS["title"]) + "  " +
            _cell(row["priority"], COL_WIDTHS["priority"]) + "  " +
            _cell(row["status"], COL_WIDTHS["status"]) + "  " +
            _cell(row["due_date"], COL_WIDTHS["due"])
        )
    print(sep)


# ── Subcommand handlers ───────────────────────────────────────────────────────

def handle_add(args):
    if args.priority not in VALID_PRIORITIES:
        print(f"Error: priority must be one of {sorted(VALID_PRIORITIES)}", file=sys.stderr)
        sys.exit(1)
    status = getattr(args, "status", "todo") or "todo"
    if status not in VALID_STATUSES:
        print(f"Error: status must be one of {sorted(VALID_STATUSES)}", file=sys.stderr)
        sys.exit(1)
    task_id = db_add(
        title=args.title,
        description=args.description or "",
        priority=args.priority,
        status=status,
        due_date=args.due_date or "",
    )
    print(f"Task {task_id} added: '{args.title}' [{args.priority}]")


def handle_list(args):
    status = getattr(args, "status", None)
    priority = getattr(args, "priority", None)
    if status and status not in VALID_STATUSES:
        print(f"Error: status must be one of {sorted(VALID_STATUSES)}", file=sys.stderr)
        sys.exit(1)
    if priority and priority not in VALID_PRIORITIES:
        print(f"Error: priority must be one of {sorted(VALID_PRIORITIES)}", file=sys.stderr)
        sys.exit(1)
    rows = db_list(status=status, priority=priority)
    print_table(rows)


def handle_update(args):
    fields = {}
    if args.title is not None:
        fields["title"] = args.title
    if args.description is not None:
        fields["description"] = args.description
    if args.priority is not None:
        if args.priority not in VALID_PRIORITIES:
            print(f"Error: priority must be one of {sorted(VALID_PRIORITIES)}", file=sys.stderr)
            sys.exit(1)
        fields["priority"] = args.priority
    if args.status is not None:
        if args.status not in VALID_STATUSES:
            print(f"Error: status must be one of {sorted(VALID_STATUSES)}", file=sys.stderr)
            sys.exit(1)
        fields["status"] = args.status
    if args.due_date is not None:
        fields["due_date"] = args.due_date
    if not fields:
        print("Nothing to update. Provide at least one field.", file=sys.stderr)
        sys.exit(1)
    count = db_update(args.id, **fields)
    if count == 0:
        print(f"Task {args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(f"Task {args.id} updated.")


def handle_done(args):
    count = db_update(args.id, status="done")
    if count == 0:
        print(f"Task {args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(f"Task {args.id} marked as done.")


def handle_delete(args):
    count = db_delete(args.id)
    if count == 0:
        print(f"Task {args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(f"Task {args.id} deleted.")


# ── Argparse wiring ───────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="task_manager",
        description="CLI Task Manager — sqlite3-backed",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("--title", required=True, help="Task title")
    p_add.add_argument("--description", default="", help="Task description")
    p_add.add_argument("--priority", default="medium", choices=sorted(VALID_PRIORITIES))
    p_add.add_argument("--status", default="todo", choices=sorted(VALID_STATUSES))
    p_add.add_argument("--due-date", dest="due_date", default="", metavar="YYYY-MM-DD")

    # list
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", choices=sorted(VALID_STATUSES), default=None)
    p_list.add_argument("--priority", choices=sorted(VALID_PRIORITIES), default=None)

    # update
    p_upd = sub.add_parser("update", help="Update a task field")
    p_upd.add_argument("id", type=int, help="Task id")
    p_upd.add_argument("--title", default=None)
    p_upd.add_argument("--description", default=None)
    p_upd.add_argument("--priority", default=None, choices=sorted(VALID_PRIORITIES))
    p_upd.add_argument("--status", default=None, choices=sorted(VALID_STATUSES))
    p_upd.add_argument("--due-date", dest="due_date", default=None, metavar="YYYY-MM-DD")

    # done
    p_done = sub.add_parser("done", help="Mark a task as done")
    p_done.add_argument("id", type=int, help="Task id")

    # delete
    p_del = sub.add_parser("delete", help="Delete a task")
    p_del.add_argument("id", type=int, help="Task id")

    return parser


def main():
    init_db()
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "add": handle_add,
        "list": handle_list,
        "update": handle_update,
        "done": handle_done,
        "delete": handle_delete,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
