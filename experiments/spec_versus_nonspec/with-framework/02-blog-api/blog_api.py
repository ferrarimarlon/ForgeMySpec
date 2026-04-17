import http.server
import sqlite3
import json
import re
import os
import sys
from datetime import datetime, timezone

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog.db")
API_KEY = "secret123"
PORT = 8080

ROUTES = [
    ("GET",    r"^/posts$",         "list_posts"),
    ("POST",   r"^/posts$",         "create_post"),
    ("GET",    r"^/posts/(\d+)$",   "get_post"),
    ("PUT",    r"^/posts/(\d+)$",   "update_post"),
    ("DELETE", r"^/posts/(\d+)$",   "delete_post"),
]


# ── DB layer ──────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                body       TEXT NOT NULL DEFAULT '',
                author     TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def _now():
    return datetime.now(timezone.utc).isoformat()


def insert_post(title, body, author):
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO posts (title, body, author, created_at, updated_at) VALUES (?,?,?,?,?)",
            (title, body, author, now, now),
        )
        row_id = cur.lastrowid
    return get_post_by_id(row_id)


def get_all_posts():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM posts ORDER BY id").fetchall()]


def get_post_by_id(post_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    return dict(row) if row else None


def update_post(post_id, fields):
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [post_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE posts SET {set_clause} WHERE id=?", values)
    return get_post_by_id(post_id)


def delete_post(post_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM posts WHERE id=?", (post_id,))


# ── HTTP handler ──────────────────────────────────────────────────────────────

class BlogHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress default per-request stderr logging

    def _check_auth(self):
        key = self.headers.get("X-API-Key", "")
        if key != API_KEY:
            self._send_json(401, {"error": "Unauthorized"})
            return False
        return True

    def _send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_no_content(self):
        self.send_response(204)
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return None

    def _route(self):
        path_matched = False
        for method, pattern, handler_name in ROUTES:
            m = re.match(pattern, self.path)
            if m:
                path_matched = True
                if self.command == method:
                    return handler_name, m.groups()
        if path_matched:
            return "_method_not_allowed", ()
        return "_not_found", ()

    def _dispatch(self):
        if not self._check_auth():
            return
        handler_name, groups = self._route()
        getattr(self, handler_name)(*groups)

    do_GET    = _dispatch
    do_POST   = _dispatch
    do_PUT    = _dispatch
    do_DELETE = _dispatch

    def _not_found(self):
        self._send_json(404, {"error": "Not found"})

    def _method_not_allowed(self):
        self._send_json(405, {"error": "Method not allowed"})

    # ── Handlers ───────────────────────────────────────────────────────────

    def list_posts(self):
        self._send_json(200, get_all_posts())

    def create_post(self):
        data = self._read_body()
        if data is None:
            self._send_json(400, {"error": "Invalid JSON"}); return
        missing = [f for f in ("title", "body", "author") if f not in data]
        if missing:
            self._send_json(400, {"error": f"Missing fields: {', '.join(missing)}"}); return
        post = insert_post(data["title"], data["body"], data["author"])
        self._send_json(201, post)

    def get_post(self, post_id):
        post = get_post_by_id(int(post_id))
        if post is None:
            self._send_json(404, {"error": f"Post {post_id} not found"}); return
        self._send_json(200, post)

    def update_post(self, post_id):
        post = get_post_by_id(int(post_id))
        if post is None:
            self._send_json(404, {"error": f"Post {post_id} not found"}); return
        data = self._read_body()
        if data is None:
            self._send_json(400, {"error": "Invalid JSON"}); return
        allowed = {k: v for k, v in data.items() if k in ("title", "body", "author")}
        updated = update_post(int(post_id), allowed)
        self._send_json(200, updated)

    def delete_post(self, post_id):
        delete_post(int(post_id))
        self._send_no_content()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    server = http.server.HTTPServer(("localhost", PORT), BlogHandler)
    print(f"Blog API listening on http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
