import ast
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import blog_api

KEY = "secret-key"


class BlogApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "t.db")
        self.start()

    def tearDown(self):
        self.stop()
        self.tmp.cleanup()

    def start(self):
        self.server = blog_api.make_server(api_key=KEY, db_path=self.db, port=0, quiet=True)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.thread.join()
        blog_api.close_server(self.server)

    def call(self, method, path, body=None, key=KEY, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if key is not None:
            req.add_header("X-API-Key", key)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.headers, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, e.headers, json.loads(e.read())

    def test_create_then_get(self):
        s, h, post = self.call("POST", "/posts", {"title": "Hi", "body": "World"})
        self.assertEqual(s, 201)
        self.assertEqual(h["Content-Type"], "application/json")
        self.assertEqual((post["title"], post["body"]), ("Hi", "World"))
        self.assertIsInstance(post["id"], int)
        s, _, got = self.call("GET", f"/posts/{post['id']}")
        self.assertEqual((s, got), (200, post))

    def test_list_and_unknown_id_404(self):
        self.assertEqual(self.call("GET", "/posts")[::2], (200, []))
        self.call("POST", "/posts", {"title": "a", "body": "b"})
        self.call("POST", "/posts", {"title": "c", "body": "d"})
        s, _, posts = self.call("GET", "/posts")
        self.assertEqual((s, [p["title"] for p in posts]), (200, ["a", "c"]))
        self.assertEqual(self.call("GET", "/posts/999")[0], 404)

    def test_update_and_delete(self):
        _, _, p = self.call("POST", "/posts", {"title": "a", "body": "b"})
        s, _, upd = self.call("PUT", f"/posts/{p['id']}", {"title": "x", "body": "y"})
        self.assertEqual((s, upd["title"], upd["body"], upd["id"]), (200, "x", "y", p["id"]))
        self.assertEqual(self.call("GET", f"/posts/{p['id']}")[2]["title"], "x")
        self.assertEqual(self.call("DELETE", f"/posts/{p['id']}")[0], 200)
        self.assertEqual(self.call("GET", f"/posts/{p['id']}")[0], 404)
        self.assertEqual(self.call("PUT", "/posts/999", {"title": "x", "body": "y"})[0], 404)
        self.assertEqual(self.call("DELETE", "/posts/999")[0], 404)

    def test_auth_required_and_no_side_effects(self):
        _, _, p = self.call("POST", "/posts", {"title": "a", "body": "b"})
        good = {"title": "z", "body": "z"}
        for key in (None, "wrong", ""):
            for method, path, body in [
                ("GET", "/posts", None), ("POST", "/posts", good),
                ("GET", f"/posts/{p['id']}", None), ("PUT", f"/posts/{p['id']}", good),
                ("DELETE", f"/posts/{p['id']}", None), ("GET", "/nope", None),
            ]:
                s, _, err = self.call(method, path, body, key=key)
                self.assertEqual(s, 401, (key, method, path))
                self.assertIn("error", err)
        s, _, posts = self.call("GET", "/posts")
        self.assertEqual(posts, [p])

    def test_invalid_bodies_400(self):
        _, _, p = self.call("POST", "/posts", {"title": "a", "body": "b"})
        bad_raw = [b"{not json", b"", b"\xff\xfe"]
        bad_json = [[], "str", 3, None, {}, {"title": "t"}, {"body": "b"},
                    {"title": "", "body": "b"}, {"title": "t", "body": "  "},
                    {"title": 1, "body": "b"}, {"title": "t", "body": ["x"]}]
        for method, path in [("POST", "/posts"), ("PUT", f"/posts/{p['id']}")]:
            for raw in bad_raw:
                s, h, err = self.call(method, path, raw=raw)
                self.assertEqual(s, 400, (method, raw))
                self.assertEqual(h["Content-Type"], "application/json")
                self.assertIn("error", err)
            for body in bad_json:
                s, h, err = self.call(method, path, raw=json.dumps(body).encode())
                self.assertEqual(s, 400, (method, body))
                self.assertIn("error", err)
        self.assertEqual(self.call("GET", "/posts")[2], [p])

    def test_defaults_and_requires_key(self):
        self.assertEqual(blog_api.HOST, "127.0.0.1")
        self.assertEqual(blog_api.PORT, 8080)
        old = os.environ.pop("BLOG_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                blog_api.make_server(db_path=self.db + "2", port=0)
            os.environ["BLOG_API_KEY"] = ""
            with self.assertRaises(ValueError):
                blog_api.make_server(db_path=self.db + "2", port=0)
            self.assertEqual(blog_api.main(), 1)
        finally:
            if old is not None:
                os.environ["BLOG_API_KEY"] = old
            else:
                os.environ.pop("BLOG_API_KEY", None)

    def test_persists_across_restart(self):
        _, _, p = self.call("POST", "/posts", {"title": "a", "body": "b"})
        self.stop()
        self.start()
        self.assertEqual(self.call("GET", f"/posts/{p['id']}")[2], p)

    def test_imports_stdlib_only(self):
        with open(blog_api.__file__) as f:
            tree = ast.parse(f.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        names = getattr(sys, "stdlib_module_names", None)
        if names is not None:
            self.assertLessEqual(mods, set(names))
            return
        # Python < 3.10: stdlib modules live under the stdlib dir, not site-packages
        import importlib.util
        import sysconfig
        stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
        for m in mods:
            spec = importlib.util.find_spec(m)
            origin = spec.origin if spec else None
            self.assertTrue(
                m in sys.builtin_module_names
                or (origin and os.path.realpath(origin).startswith(stdlib)
                    and "site-packages" not in origin),
                m)


if __name__ == "__main__":
    unittest.main()
