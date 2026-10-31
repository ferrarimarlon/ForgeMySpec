"""REST Blog API: standard library only (http.server + sqlite3), single file.

Environment:
  BLOG_API_KEY  required, the value clients must send in the X-API-Key header
  BLOG_DB_PATH  SQLite file path (default: blog.db)
"""
import hmac
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_DB_PATH = "blog.db"
MAX_BODY = 1024 * 1024

POST_PATH = re.compile(r"^/posts/(\d+)$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path):
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(SCHEMA)
    finally:
        conn.close()


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _validate_payload(data):
    if not isinstance(data, dict):
        raise ApiError(400, "body must be a JSON object")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ApiError(400, "title is required and must be a non-empty string")
    content = data.get("content", "")
    if not isinstance(content, str):
        raise ApiError(400, "content must be a string")
    return title, content


class BlogHandler(BaseHTTPRequestHandler):
    server_version = "BlogAPI/1.0"

    # -- plumbing ---------------------------------------------------------
    def log_message(self, fmt, *args):  # never log headers (API key)
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if status != 204:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if status != 204:
            self.wfile.write(body)

    def _authorized(self):
        supplied = self.headers.get("X-API-Key", "")
        return hmac.compare_digest(
            supplied.encode("utf-8"), self.server.api_key.encode("utf-8")
        )

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "invalid Content-Length")
        if length <= 0:
            raise ApiError(400, "request body is required")
        if length > MAX_BODY:
            raise ApiError(400, "request body too large")
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
            conn = _connect(self.server.db_path)
            try:
                self._route(conn, method, path)
            finally:
                conn.close()
        except ApiError as exc:
            self._send(exc.status, {"error": exc.message})
        except Exception:
            self._send(500, {"error": "internal server error"})

    # -- routing ----------------------------------------------------------
    def _route(self, conn, method, path):
        match = POST_PATH.match(path)
        if path == "/posts":
            if method == "GET":
                rows = conn.execute("SELECT * FROM posts ORDER BY id").fetchall()
                return self._send(200, [dict(r) for r in rows])
            if method == "POST":
                return self._create(conn)
            raise ApiError(405, "method not allowed")
        if match:
            post_id = int(match.group(1))
            if method == "GET":
                return self._send(200, self._get(conn, post_id))
            if method == "PUT":
                return self._update(conn, post_id)
            if method == "DELETE":
                self._get(conn, post_id)
                with conn:
                    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
                return self._send(204)
            raise ApiError(405, "method not allowed")
        raise ApiError(404, "not found")

    @staticmethod
    def _get(conn, post_id):
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            raise ApiError(404, "post not found")
        return dict(row)

    def _create(self, conn):
        title, content = _validate_payload(self._read_json())
        now = _now()
        with conn:
            cur = conn.execute(
                "INSERT INTO posts (title, content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (title, content, now, now),
            )
        self._send(201, self._get(conn, cur.lastrowid))

    def _update(self, conn, post_id):
        self._get(conn, post_id)
        title, content = _validate_payload(self._read_json())
        with conn:
            conn.execute(
                "UPDATE posts SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (title, content, _now(), post_id),
            )
        self._send(200, self._get(conn, post_id))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PATCH(self):
        self._dispatch("PATCH")


def create_server(api_key, db_path=DEFAULT_DB_PATH, host=DEFAULT_HOST, port=DEFAULT_PORT):
    if not api_key:
        raise ValueError("an API key is required")
    init_db(db_path)
    server = ThreadingHTTPServer((host, port), BlogHandler)
    server.api_key = api_key
    server.db_path = db_path
    return server


def main():
    api_key = os.environ.get("BLOG_API_KEY", "")
    if not api_key:
        sys.exit("BLOG_API_KEY must be set to a non-empty value")
    server = create_server(api_key, os.environ.get("BLOG_DB_PATH", DEFAULT_DB_PATH))
    print("Blog API listening on http://%s:%d" % (DEFAULT_HOST, DEFAULT_PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
