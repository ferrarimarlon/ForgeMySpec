#!/usr/bin/env python3
"""Blog REST API using only the standard library (http.server + sqlite3).

Run:   BLOG_API_KEY=secret python3 blog_api.py
Auth:  send header  X-API-Key: <key>   (default key "dev-key" if env unset)

Endpoints (JSON in/out):
  GET    /posts          list posts (?limit=&offset=)
  POST   /posts          create {title, content, author?}
  GET    /posts/<id>     read
  PUT    /posts/<id>     replace {title, content, author?}
  PATCH  /posts/<id>     partial update
  DELETE /posts/<id>     delete
"""
import hmac
import json
import os
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

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
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            )"""
        )


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


FIELDS = ("title", "content", "author")


def validate(data, partial):
    if not isinstance(data, dict):
        raise ApiError(400, "body must be a JSON object")
    out = {}
    for f in FIELDS:
        if f in data:
            if not isinstance(data[f], str):
                raise ApiError(422, f"'{f}' must be a string")
            out[f] = data[f].strip() if f != "content" else data[f]
    if not partial:
        for f in ("title", "content"):
            if not out.get(f):
                raise ApiError(422, f"'{f}' is required")
    else:
        for f in ("title", "content"):
            if f in out and not out[f]:
                raise ApiError(422, f"'{f}' must not be empty")
        if not out:
            raise ApiError(422, "no updatable fields provided")
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "BlogAPI/1.0"

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
            raise ApiError(413, "body too large")
        try:
            return json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "invalid JSON")

    def _auth(self):
        key = self.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key.encode(), API_KEY.encode()):
            raise ApiError(401, "missing or invalid API key")

    def _handle(self, method):
        try:
            self._auth()
            url = urlparse(self.path)
            m = re.fullmatch(r"/posts(?:/(\d+))?/?", url.path)
            if not m:
                raise ApiError(404, "not found")
            pid = int(m.group(1)) if m.group(1) else None
            self._route(method, pid, parse_qs(url.query))
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except Exception:
            self._send(500, {"error": "internal server error"})
            raise

    def _route(self, method, pid, query):
        c = db()
        if pid is None:
            if method == "GET":
                try:
                    limit = min(max(int(query.get("limit", ["50"])[0]), 1), 200)
                    offset = max(int(query.get("offset", ["0"])[0]), 0)
                except ValueError:
                    raise ApiError(400, "limit/offset must be integers")
                rows = c.execute(
                    "SELECT * FROM posts ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
                return self._send(200, [dict(r) for r in rows])
            if method == "POST":
                d = validate(self._body(), partial=False)
                with c:
                    cur = c.execute(
                        "INSERT INTO posts (title, content, author) VALUES (?,?,?)",
                        (d["title"], d["content"], d.get("author", "")),
                    )
                row = c.execute("SELECT * FROM posts WHERE id=?", (cur.lastrowid,)).fetchone()
                return self._send(201, dict(row))
            raise ApiError(405, "method not allowed")

        row = c.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if row is None:
            raise ApiError(404, "post not found")
        if method == "GET":
            return self._send(200, dict(row))
        if method in ("PUT", "PATCH"):
            d = validate(self._body(), partial=(method == "PATCH"))
            if method == "PUT":
                d.setdefault("author", "")
            sets = ", ".join(f"{k}=?" for k in d)
            with c:
                c.execute(
                    f"UPDATE posts SET {sets}, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
                    (*d.values(), pid),
                )
            row = c.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
            return self._send(200, dict(row))
        if method == "DELETE":
            with c:
                c.execute("DELETE FROM posts WHERE id=?", (pid,))
            return self._send(204)
        raise ApiError(405, "method not allowed")

    def do_GET(self): self._handle("GET")
    def do_POST(self): self._handle("POST")
    def do_PUT(self): self._handle("PUT")
    def do_PATCH(self): self._handle("PATCH")
    def do_DELETE(self): self._handle("DELETE")


def main():
    init_db()
    if "BLOG_API_KEY" not in os.environ:
        print("WARNING: BLOG_API_KEY not set; using insecure default 'dev-key'")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Blog API listening on http://{HOST}:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
