#!/usr/bin/env python3
"""Blog REST API using only the standard library (http.server + sqlite3).

Run:    BLOG_API_KEY=secret python3 blog_api.py
Auth:   send header "X-API-Key: <key>" on every request.

Endpoints:
    GET    /posts          list posts (?limit=&offset=)
    POST   /posts          create {"title", "content", "author"?}
    GET    /posts/<id>     read one
    PUT    /posts/<id>     replace {"title", "content", "author"?}
    PATCH  /posts/<id>     partial update
    DELETE /posts/<id>     delete
"""
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8080
DB_PATH = os.environ.get("BLOG_DB", "blog.db")
MAX_BODY = 1_000_000
FIELDS = ("title", "content", "author")

API_KEY = os.environ.get("BLOG_API_KEY")
if not API_KEY:
    API_KEY = secrets.token_urlsafe(24)
    print(f"BLOG_API_KEY not set; generated key: {API_KEY}")

_local = threading.local()


def db():
    """One sqlite connection per thread."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def init_db():
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def validate(data, partial):
    if not isinstance(data, dict):
        raise ApiError(400, "JSON body must be an object")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ApiError(400, f"Unknown fields: {', '.join(sorted(unknown))}")
    out = {}
    for f in FIELDS:
        if f in data:
            if not isinstance(data[f], str):
                raise ApiError(400, f"'{f}' must be a string")
            out[f] = data[f]
        elif not partial and f in ("title", "content"):
            raise ApiError(400, f"'{f}' is required")
    for f in ("title", "content"):
        if f in out and not out[f].strip():
            raise ApiError(400, f"'{f}' must not be empty")
    if partial and not out:
        raise ApiError(400, "No updatable fields provided")
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "BlogAPI/1.0"

    # -- helpers ---------------------------------------------------------
    def send_json(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "Invalid Content-Length")
        if length <= 0:
            raise ApiError(400, "JSON body required")
        if length > MAX_BODY:
            raise ApiError(413, "Body too large")
        try:
            return json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Invalid JSON")

    def authorized(self):
        key = self.headers.get("X-API-Key", "")
        return hmac.compare_digest(key.encode(), API_KEY.encode())

    def route(self):
        m = re.fullmatch(r"/posts(?:/(\d+))?/?", self.path.split("?", 1)[0])
        if not m:
            raise ApiError(404, "Not found")
        return int(m.group(1)) if m.group(1) else None

    def query(self):
        from urllib.parse import parse_qs, urlsplit

        q = parse_qs(urlsplit(self.path).query)
        try:
            limit = min(max(int(q.get("limit", ["50"])[0]), 1), 200)
            offset = max(int(q.get("offset", ["0"])[0]), 0)
        except ValueError:
            raise ApiError(400, "limit/offset must be integers")
        return limit, offset

    def fetch(self, post_id):
        row = db().execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            raise ApiError(404, "Post not found")
        return dict(row)

    # -- dispatch --------------------------------------------------------
    def handle_request(self):
        try:
            if not self.authorized():
                raise ApiError(401, "Missing or invalid X-API-Key")
            post_id = self.route()
            getattr(self, f"do_{self.command}_impl")(post_id)
        except ApiError as e:
            self.send_json(e.status, {"error": e.message})
        except Exception as e:  # noqa: BLE001
            self.log_error("Unhandled error: %r", e)
            self.send_json(500, {"error": "Internal server error"})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_request

    # -- operations ------------------------------------------------------
    def do_GET_impl(self, post_id):
        if post_id is None:
            limit, offset = self.query()
            rows = db().execute(
                "SELECT * FROM posts ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
            self.send_json(200, [dict(r) for r in rows])
        else:
            self.send_json(200, self.fetch(post_id))

    def do_POST_impl(self, post_id):
        if post_id is not None:
            raise ApiError(405, "Method not allowed")
        data = validate(self.read_json(), partial=False)
        ts = now()
        with db() as c:
            cur = c.execute(
                "INSERT INTO posts (title, content, author, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (data["title"], data["content"], data.get("author", ""), ts, ts),
            )
        post = self.fetch(cur.lastrowid)
        self.send_json(201, post)

    def _update(self, post_id, partial):
        if post_id is None:
            raise ApiError(405, "Method not allowed")
        self.fetch(post_id)
        data = validate(self.read_json(), partial=partial)
        if not partial:
            data.setdefault("author", "")
        sets = ", ".join(f"{k} = ?" for k in data)
        with db() as c:
            c.execute(
                f"UPDATE posts SET {sets}, updated_at = ? WHERE id = ?",
                (*data.values(), now(), post_id),
            )
        self.send_json(200, self.fetch(post_id))

    def do_PUT_impl(self, post_id):
        self._update(post_id, partial=False)

    def do_PATCH_impl(self, post_id):
        self._update(post_id, partial=True)

    def do_DELETE_impl(self, post_id):
        if post_id is None:
            raise ApiError(405, "Method not allowed")
        self.fetch(post_id)
        with db() as c:
            c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        self.send_json(204)


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Blog API listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
