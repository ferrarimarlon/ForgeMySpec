import http.server
import sqlite3
import json
import re
import os
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog.db")
API_KEY = "secret123"

def init_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, body TEXT, author TEXT,
        created_at TEXT, updated_at TEXT)""")
    con.commit()
    return con

def now():
    return datetime.now(timezone.utc).isoformat()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def auth(self):
        if self.headers.get("X-API-Key") != API_KEY:
            self.respond(401, {"error": "Unauthorized"})
            return False
        return True

    def respond(self, code, data=None):
        body = json.dumps(data).encode() if data is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def body(self):
        l = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(l)) if l else {}

    def do_GET(self):
        if not self.auth(): return
        if self.path == "/posts":
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            rows = [dict(r) for r in con.execute("SELECT * FROM posts").fetchall()]
            self.respond(200, rows)
        elif m := re.match(r"^/posts/(\d+)$", self.path):
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT * FROM posts WHERE id=?", (m.group(1),)).fetchone()
            if row: self.respond(200, dict(row))
            else: self.respond(404, {"error": "Not found"})
        else:
            self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.auth(): return
        if self.path == "/posts":
            data = self.body()
            t = now()
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "INSERT INTO posts(title,body,author,created_at,updated_at) VALUES(?,?,?,?,?)",
                (data.get("title"), data.get("body"), data.get("author"), t, t))
            con.commit()
            row = con.execute("SELECT * FROM posts WHERE id=?", (cur.lastrowid,)).fetchone()
            self.respond(201, dict(row))
        else:
            self.respond(404, {"error": "Not found"})

    def do_PUT(self):
        if not self.auth(): return
        if m := re.match(r"^/posts/(\d+)$", self.path):
            data = self.body()
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            fields = {k: v for k, v in data.items() if k in ("title", "body", "author")}
            fields["updated_at"] = now()
            set_q = ", ".join(f"{k}=?" for k in fields)
            con.execute(f"UPDATE posts SET {set_q} WHERE id=?", [*fields.values(), m.group(1)])
            con.commit()
            row = con.execute("SELECT * FROM posts WHERE id=?", (m.group(1),)).fetchone()
            self.respond(200, dict(row) if row else None)
        else:
            self.respond(404, {"error": "Not found"})

    def do_DELETE(self):
        if not self.auth(): return
        if m := re.match(r"^/posts/(\d+)$", self.path):
            con = sqlite3.connect(DB)
            con.execute("DELETE FROM posts WHERE id=?", (m.group(1),))
            con.commit()
            self.send_response(204)
            self.end_headers()
        else:
            self.respond(404, {"error": "Not found"})

if __name__ == "__main__":
    init_db()
    s = http.server.HTTPServer(("localhost", 8080), Handler)
    print("Listening on :8080")
    s.serve_forever()
