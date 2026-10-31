"""REST Blog API: standard library only (http.server + sqlite3).

Routes (all require the X-API-Key header, all bodies are JSON):
    POST   /posts        create   {"title": str, "content": str}
    GET    /posts        list
    GET    /posts/<id>   read
    PUT    /posts/<id>   update   {"title": str, "content": str}
    DELETE /posts/<id>   delete

Environment: BLOG_API_KEY (default "dev-key"), BLOG_DB (default "blog.db").
"""
import hmac
import json
import os
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8080
DEFAULT_KEY = "dev-key"
DEFAULT_DB = "blog.db"
MAX_BODY = 1_000_000

_POST_PATH = re.compile(r"^/posts/(\d+)$")


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS posts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '')"
        )
        conn.commit()
    finally:
        conn.close()


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _row(r):
    return {"id": r[0], "title": r[1], "content": r[2]}


class Handler(BaseHTTPRequestHandler):
    server_version = "BlogAPI/1.0"

    def log_message(self, fmt, *args):  # keep output quiet
        pass

    # -- helpers ---------------------------------------------------------
    def _send(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorized(self):
        supplied = self.headers.get("X-API-Key")
        if supplied is None:
            return False
        return hmac.compare_digest(supplied.encode("utf-8"), self.server.api_key.encode("utf-8"))

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "invalid Content-Length")
        if length <= 0 or length > MAX_BODY:
            raise ApiError(400, "a JSON body is required")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "malformed JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "JSON body must be an object")
        title = data.get("title")
        content = data.get("content", "")
        if not isinstance(title, str) or not title.strip():
            raise ApiError(400, "title must be a non-empty string")
        if not isinstance(content, str):
            raise ApiError(400, "content must be a string")
        return title, content

    def _dispatch(self):
        try:
            # Auth first: nothing below runs (or touches the DB) without a valid key.
            if not self._authorized():
                raise ApiError(401, "missing or invalid X-API-Key")
            path = self.path.split("?", 1)[0]
            match = _POST_PATH.match(path)
            if path == "/posts" and self.command in ("GET", "POST"):
                self._collection()
            elif match and self.command in ("GET", "PUT", "DELETE"):
                self._item(int(match.group(1)))
            elif path == "/posts" or match:
                raise ApiError(405, "method not allowed")
            else:
                raise ApiError(404, "not found")
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except sqlite3.Error:
            self._send(500, {"error": "database error"})

    def _collection(self):
        conn = sqlite3.connect(self.server.db_path)
        try:
            if self.command == "GET":
                rows = conn.execute("SELECT id, title, content FROM posts ORDER BY id").fetchall()
                self._send(200, [_row(r) for r in rows])
            else:
                title, content = self._read_json()
                cur = conn.execute("INSERT INTO posts (title, content) VALUES (?, ?)", (title, content))
                conn.commit()
                self._send(201, {"id": cur.lastrowid, "title": title, "content": content})
        finally:
            conn.close()

    def _item(self, post_id):
        conn = sqlite3.connect(self.server.db_path)
        try:
            if self.command == "PUT":
                title, content = self._read_json()
                cur = conn.execute(
                    "UPDATE posts SET title = ?, content = ? WHERE id = ?", (title, content, post_id)
                )
                conn.commit()
                if cur.rowcount == 0:
                    raise ApiError(404, "post not found")
                self._send(200, {"id": post_id, "title": title, "content": content})
            elif self.command == "DELETE":
                cur = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
                conn.commit()
                if cur.rowcount == 0:
                    raise ApiError(404, "post not found")
                self._send(200, {"deleted": post_id})
            else:
                r = conn.execute("SELECT id, title, content FROM posts WHERE id = ?", (post_id,)).fetchone()
                if r is None:
                    raise ApiError(404, "post not found")
                self._send(200, _row(r))
        finally:
            conn.close()

    do_GET = do_POST = do_PUT = do_DELETE = _dispatch

    def do_PATCH(self):
        self._dispatch()


def make_server(host=HOST, port=PORT, db_path=None, api_key=None):
    db_path = db_path or os.environ.get("BLOG_DB", DEFAULT_DB)
    api_key = api_key or os.environ.get("BLOG_API_KEY", DEFAULT_KEY)
    init_db(db_path)
    server = ThreadingHTTPServer((host, port), Handler)
    server.db_path = db_path
    server.api_key = api_key
    return server


def main():
    server = make_server()
    print("Blog API listening on http://%s:%d" % (HOST, PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
