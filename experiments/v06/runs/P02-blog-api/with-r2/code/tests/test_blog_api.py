import ast
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import blog_api  # noqa: E402

KEY = "test-key"


class BlogApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = blog_api.create_server(
            KEY, os.path.join(self.tmp.name, "t.db"), port=0
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def call(self, method, path, body=None, key=KEY, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if key is not None:
            headers["X-API-Key"] = key
        data = raw
        if body is not None:
            data = json.dumps(body)
        if data is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read().decode()
        conn.close()
        return resp.status, (json.loads(text) if text else None)

    def test_create_post(self):
        status, post = self.call("POST", "/posts", {"title": "Hi", "content": "Body"})
        self.assertEqual(status, 201)
        self.assertEqual(post["title"], "Hi")
        self.assertEqual(post["content"], "Body")
        self.assertIsInstance(post["id"], int)
        self.assertIn("created_at", post)
        self.assertIn("updated_at", post)
        self.assertEqual(self.call("GET", "/posts/%d" % post["id"])[1], post)

    def test_read_posts(self):
        self.assertEqual(self.call("GET", "/posts"), (200, []))
        a = self.call("POST", "/posts", {"title": "A"})[1]
        b = self.call("POST", "/posts", {"title": "B", "content": "x"})[1]
        status, posts = self.call("GET", "/posts")
        self.assertEqual(status, 200)
        self.assertEqual([p["id"] for p in posts], [a["id"], b["id"]])
        self.assertEqual(self.call("GET", "/posts/%d" % b["id"]), (200, b))
        self.assertEqual(self.call("GET", "/posts/999")[0], 404)

    def test_update_post(self):
        post = self.call("POST", "/posts", {"title": "Old", "content": "old"})[1]
        status, new = self.call(
            "PUT", "/posts/%d" % post["id"], {"title": "New", "content": "new"}
        )
        self.assertEqual(status, 200)
        self.assertEqual((new["title"], new["content"]), ("New", "new"))
        self.assertEqual(new["id"], post["id"])
        self.assertEqual(new["created_at"], post["created_at"])
        self.assertEqual(self.call("GET", "/posts/%d" % post["id"])[1], new)
        self.assertEqual(self.call("PUT", "/posts/999", {"title": "x"})[0], 404)

    def test_delete_post(self):
        post = self.call("POST", "/posts", {"title": "Gone"})[1]
        self.assertEqual(self.call("DELETE", "/posts/%d" % post["id"]), (204, None))
        self.assertEqual(self.call("GET", "/posts/%d" % post["id"])[0], 404)
        self.assertEqual(self.call("DELETE", "/posts/%d" % post["id"])[0], 404)

    def test_auth_required(self):
        post = self.call("POST", "/posts", {"title": "Keep"})[1]
        pid = "/posts/%d" % post["id"]
        for key in (None, "wrong", ""):
            for method, path, body in (
                ("GET", "/posts", None),
                ("POST", "/posts", {"title": "Evil"}),
                ("GET", pid, None),
                ("PUT", pid, {"title": "Evil"}),
                ("DELETE", pid, None),
                ("GET", "/nope", None),
            ):
                status, resp = self.call(method, path, body, key=key)
                self.assertEqual(status, 401, (method, path, key))
                self.assertIn("error", resp)
        status, posts = self.call("GET", "/posts")
        self.assertEqual(posts, [post])

    def test_json_validation(self):
        for raw in ("{not json", "[1,2]", '"str"', ""):
            self.assertEqual(self.call("POST", "/posts", raw=raw)[0], 400, raw)
        for body in ({}, {"title": ""}, {"title": "   "}, {"title": 5},
                     {"title": "ok", "content": 7}):
            status, resp = self.call("POST", "/posts", body)
            self.assertEqual(status, 400, body)
            self.assertIn("error", resp)
        post = self.call("POST", "/posts", {"title": "ok"})[1]
        self.assertEqual(
            self.call("PUT", "/posts/%d" % post["id"], {"content": "x"})[0], 400
        )
        self.assertEqual(self.call("GET", "/posts")[1][0]["title"], "ok")

    def test_default_bind(self):
        self.assertEqual(blog_api.DEFAULT_HOST, "127.0.0.1")
        self.assertEqual(blog_api.DEFAULT_PORT, 8080)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        with self.assertRaises(ValueError):
            blog_api.create_server("")

    def test_stdlib_single_file(self):
        with open(os.path.join(ROOT, "blog_api.py")) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        allowed = {"hmac", "json", "os", "re", "sqlite3", "sys", "datetime", "http"}
        self.assertTrue(mods <= allowed, mods)


if __name__ == "__main__":
    unittest.main()
