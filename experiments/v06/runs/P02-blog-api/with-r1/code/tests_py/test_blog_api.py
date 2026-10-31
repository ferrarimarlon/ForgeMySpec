import ast
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest

import blog_api

KEY = "test-key"
ROOT = os.path.dirname(os.path.abspath(blog_api.__file__))


class ApiCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = blog_api.make_server("127.0.0.1", 0, os.path.join(self.tmp.name, "t.db"), KEY)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, key=KEY, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if key is not None:
            headers["X-API-Key"] = key
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read().decode()
        conn.close()
        return resp.status, (json.loads(text) if text else None)


class CrudTests(ApiCase):
    def test_create_list_get(self):
        st, post = self.call("POST", "/posts", {"title": "Hello", "content": "World"})
        self.assertEqual(st, 201)
        self.assertEqual(post, {"id": post["id"], "title": "Hello", "content": "World"})
        self.assertEqual(self.call("GET", "/posts"), (200, [post]))
        self.assertEqual(self.call("GET", "/posts/%d" % post["id"]), (200, post))
        st, err = self.call("GET", "/posts/999")
        self.assertEqual(st, 404)
        self.assertIn("error", err)

    def test_update_delete_and_404(self):
        _, post = self.call("POST", "/posts", {"title": "A", "content": "B"})
        pid = post["id"]
        st, upd = self.call("PUT", "/posts/%d" % pid, {"title": "A2", "content": "B2"})
        self.assertEqual((st, upd), (200, {"id": pid, "title": "A2", "content": "B2"}))
        self.assertEqual(self.call("GET", "/posts/%d" % pid)[1]["title"], "A2")
        self.assertEqual(self.call("DELETE", "/posts/%d" % pid)[0], 200)
        self.assertEqual(self.call("GET", "/posts/%d" % pid)[0], 404)
        self.assertEqual(self.call("PUT", "/posts/%d" % pid, {"title": "x"})[0], 404)
        self.assertEqual(self.call("DELETE", "/posts/%d" % pid)[0], 404)


class AuthTests(ApiCase):
    def test_missing_or_wrong_key_is_401(self):
        _, post = self.call("POST", "/posts", {"title": "Keep", "content": "me"})
        pid = post["id"]
        for key in (None, "wrong", ""):
            for method, path, body in [
                ("GET", "/posts", None),
                ("POST", "/posts", {"title": "evil"}),
                ("GET", "/posts/%d" % pid, None),
                ("PUT", "/posts/%d" % pid, {"title": "evil"}),
                ("DELETE", "/posts/%d" % pid, None),
                ("GET", "/nowhere", None),
            ]:
                st, err = self.call(method, path, body, key=key)
                self.assertEqual(st, 401, (key, method, path))
                self.assertIn("error", err)
        self.assertEqual(self.call("GET", "/posts"), (200, [post]))


class JsonTests(ApiCase):
    def test_bad_json_is_400(self):
        for raw in (b"{not json", b"[1,2]", b"", b'{"content": "no title"}', b'{"title": ""}',
                    b'{"title": 5}', b'{"title": "t", "content": 3}'):
            st, err = self.call("POST", "/posts", raw=raw)
            self.assertEqual(st, 400, raw)
            self.assertIn("error", err)
        _, post = self.call("POST", "/posts", {"title": "ok"})
        self.assertEqual(self.call("PUT", "/posts/%d" % post["id"], raw=b"{bad")[0], 400)
        self.assertEqual(self.call("GET", "/posts")[1], [{"id": post["id"], "title": "ok", "content": ""}])


class ServerTests(unittest.TestCase):
    def test_default_address(self):
        self.assertEqual((blog_api.HOST, blog_api.PORT), ("127.0.0.1", 8080))

    def test_stdlib_only_single_file(self):
        with open(os.path.join(ROOT, "blog_api.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        allowed = {"hmac", "http", "json", "os", "re", "sqlite3"}
        self.assertLessEqual(mods, allowed)
        self.assertIn("http", mods)
        self.assertIn("sqlite3", mods)


if __name__ == "__main__":
    unittest.main()
