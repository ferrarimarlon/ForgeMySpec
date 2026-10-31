#!/usr/bin/env python3
"""REST Blog API: standard library only (http.server + sqlite3).

Environment:
  BLOG_API_KEY  required; value clients must send in the X-API-Key header
  BLOG_DB_PATH  SQLite file path (default: blog.db)

Routes (all JSON, all require X-API-Key):
  POST   /posts        create   -> 201
  GET    /posts        list     -> 200
  GET    /posts/{id}   read     -> 200 / 404
  PUT    /posts/{id}   replace  -> 200 / 404
  DELETE /posts/{id}   delete   -> 200 / 404
"""
import hmac
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8080
MAX_BODY = 1024 * 1024
POST_PATH = re.compile(r"^/posts/(\d+)$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_to_post(row):
    return {"id": row[0], "title": row[1], "body": row[2],
            "created_at": row[3], "updated_at": row[4]}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def validate_post(data):
    if not isinstance(data, dict):
        raise ApiError(400, "body must be a JSON object")
    for field in ("title", "body"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ApiError(400, f"'{field}' is required and must be a non-empty string")
    return data["title"], data["body"]


class Handler(BaseHTTPRequestHandler):
    server_version = "BlogApi/1.0"

    def log_message(self, fmt, *args):
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    # -- plumbing ----------------------------------------------------------
    def _send(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        supplied = self.headers.get("X-API-Key") or ""
        return hmac.compare_digest(supplied.encode("utf-8"),
                                   self.server.api_key.encode("utf-8"))

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "invalid Content-Length")
        if length <= 0:
            raise ApiError(400, "request body is required")
        if length > MAX_BODY:
            raise ApiError(413, "request body too large")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "malformed JSON")

    def _dispatch(self, method):
        try:
            if not self._authorized():
                raise ApiError(401, "missing or invalid X-API-Key")
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            match = POST_PATH.match(path)
            if path == "/posts" and method == "GET":
                return self._send(200, self._list())
            if path == "/posts" and method == "POST":
                return self._send(201, self._create(self._read_json()))
            if match:
                pid = int(match.group(1))
                if method == "GET":
                    return self._send(200, self._get(pid))
                if method == "PUT":
                    return self._send(200, self._update(pid, self._read_json()))
                if method == "DELETE":
                    self._delete(pid)
                    return self._send(200, {"deleted": pid})
            if path == "/posts" or match:
                raise ApiError(405, "method not allowed")
            raise ApiError(404, "not found")
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except Exception:
            self._send(500, {"error": "internal server error"})

    do_GET = lambda self: self._dispatch("GET")
    do_POST = lambda self: self._dispatch("POST")
    do_PUT = lambda self: self._dispatch("PUT")
    do_DELETE = lambda self: self._dispatch("DELETE")
    do_PATCH = lambda self: self._dispatch("PATCH")

    # -- storage -----------------------------------------------------------
    def _query(self, sql, params=(), write=False):
        with self.server.db_lock:
            cur = self.server.db.execute(sql, params)
            rows = cur.fetchall()
            if write:
                self.server.db.commit()
            return rows, cur

    def _list(self):
        rows, _ = self._query("SELECT id,title,body,created_at,updated_at FROM posts ORDER BY id")
        return [row_to_post(r) for r in rows]

    def _get(self, pid):
        rows, _ = self._query(
            "SELECT id,title,body,created_at,updated_at FROM posts WHERE id=?", (pid,))
        if not rows:
            raise ApiError(404, "post not found")
        return row_to_post(rows[0])

    def _create(self, data):
        title, body = validate_post(data)
        ts = now()
        _, cur = self._query(
            "INSERT INTO posts (title,body,created_at,updated_at) VALUES (?,?,?,?)",
            (title, body, ts, ts), write=True)
        return self._get(cur.lastrowid)

    def _update(self, pid, data):
        title, body = validate_post(data)
        _, cur = self._query(
            "UPDATE posts SET title=?, body=?, updated_at=? WHERE id=?",
            (title, body, now(), pid), write=True)
        if cur.rowcount == 0:
            raise ApiError(404, "post not found")
        return self._get(pid)

    def _delete(self, pid):
        _, cur = self._query("DELETE FROM posts WHERE id=?", (pid,), write=True)
        if cur.rowcount == 0:
            raise ApiError(404, "post not found")


def make_server(api_key=None, db_path=None, host=HOST, port=PORT, quiet=False):
    """Build (but do not start) the server. Raises ValueError without an API key."""
    api_key = os.environ.get("BLOG_API_KEY", "") if api_key is None else api_key
    if not api_key:
        raise ValueError("BLOG_API_KEY must be set to a non-empty value")
    db_path = db_path or os.environ.get("BLOG_DB_PATH", "blog.db")
    import threading
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute(SCHEMA)
    db.commit()
    server = ThreadingHTTPServer((host, port), Handler)
    server.api_key = api_key
    server.db = db
    server.db_lock = threading.Lock()
    server.quiet = quiet
    return server


def close_server(server):
    server.server_close()
    server.db.close()


def main():
    try:
        server = make_server()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Blog API listening on http://localhost:{PORT}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        close_server(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
