#!/usr/bin/env python3
"""Blog REST API using only the standard library.

Run:  BLOG_API_KEY=secret python3 blog_api.py
Auth: send header  X-API-Key: <key>  (default key "dev-key" if env unset).

Endpoints:
  GET    /posts        list posts (?limit=&offset=)
  POST   /posts        create  {"title": ..., "content": ..., "author": ...}
  GET    /posts/<id>   read
  PUT    /posts/<id>   replace (title, content required)
  PATCH  /posts/<id>   partial update
  DELETE /posts/<id>   delete
"""
import hmac
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8080
DB_PATH = os.environ.get("BLOG_DB", "blog.db")
API_KEY = os.environ.get("BLOG_API_KEY", "dev-key")
MAX_BODY = 1_000_000

_local = threading.local()


def db():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
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


FIELDS = ("title", "content", "author")


def validate(data, partial):
    if not isinstance(data, dict):
        raise ApiError(400, "JSON body must be an object")
    clean = {}
    for f in FIELDS:
        if f in data:
            if not isinstance(data[f], str):
                raise ApiError(400, f"'{f}' must be a string")
            clean[f] = data[f]
    for f in ("title", "content"):
        if f in clean and not clean[f].strip():
            raise ApiError(400, f"'{f}' must not be empty")
        if not partial and f not in clean:
            raise ApiError(400, f"'{f}' is required")
    if partial and not clean:
        raise ApiError(400, "no updatable fields provided")
    return clean


class Handler(BaseHTTPRequestHandler):
    server_version = "BlogAPI/1.0"
    ROUTE = re.compile(r"^/posts(?:/(\d+))?/?$")

    def _send(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "invalid Content-Length")
        if length <= 0:
            raise ApiError(400, "request body required")
        if length > MAX_BODY:
            raise ApiError(413, "request body too large")
        try:
            return json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "invalid JSON")

    def _dispatch(self, method):
        try:
            path, _, query = self.path.partition("?")
            m = self.ROUTE.match(path)
            if not m:
                raise ApiError(404, "not found")
            supplied = self.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied.encode(), API_KEY.encode()):
                raise ApiError(401, "missing or invalid API key")
            pid = int(m.group(1)) if m.group(1) else None
            handler = getattr(self, f"_{method}_{'item' if pid else 'coll'}", None)
            if handler is None:
                raise ApiError(405, "method not allowed")
            handler(pid, query) if pid is None else handler(pid)
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except Exception:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": "internal server error"})

    def _get_row(self, pid):
        row = db().execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if row is None:
            raise ApiError(404, "post not found")
        return row

    # collection
    def _GET_coll(self, _pid, query):
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        try:
            limit = min(max(int(params.get("limit", 50)), 1), 200)
            offset = max(int(params.get("offset", 0)), 0)
        except ValueError:
            raise ApiError(400, "limit/offset must be integers")
        rows = db().execute(
            "SELECT * FROM posts ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        self._send(200, [dict(r) for r in rows])

    def _POST_coll(self, _pid, _query):
        d = validate(self._body(), partial=False)
        d.setdefault("author", "")
        ts = now()
        conn = db()
        cur = conn.execute(
            "INSERT INTO posts (title, content, author, created_at, updated_at)"
            " VALUES (?,?,?,?,?)",
            (d["title"], d["content"], d["author"], ts, ts),
        )
        conn.commit()
        self._send(201, dict(self._get_row(cur.lastrowid)))

    # item
    def _GET_item(self, pid):
        self._send(200, dict(self._get_row(pid)))

    def _update(self, pid, partial):
        d = validate(self._body(), partial)
        row = self._get_row(pid)
        if not partial:
            d.setdefault("author", "")
        merged = {**dict(row), **d, "updated_at": now()}
        conn = db()
        conn.execute(
            "UPDATE posts SET title=?, content=?, author=?, updated_at=? WHERE id=?",
            (merged["title"], merged["content"], merged["author"],
             merged["updated_at"], pid),
        )
        conn.commit()
        self._send(200, dict(self._get_row(pid)))

    def _PUT_item(self, pid):
        self._update(pid, partial=False)

    def _PATCH_item(self, pid):
        self._update(pid, partial=True)

    def _DELETE_item(self, pid):
        self._get_row(pid)
        conn = db()
        conn.execute("DELETE FROM posts WHERE id=?", (pid,))
        conn.commit()
        self._send(204)

    def do_GET(self): self._dispatch("GET")
    def do_POST(self): self._dispatch("POST")
    def do_PUT(self): self._dispatch("PUT")
    def do_PATCH(self): self._dispatch("PATCH")
    def do_DELETE(self): self._dispatch("DELETE")


def main():
    init_db()
    if API_KEY == "dev-key":
        print("WARNING: using default API key 'dev-key'; set BLOG_API_KEY")
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
