import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import config_validator as cv


class ValidatorTests(unittest.TestCase):
    def test_required_fields(self):
        schema = {"required": ["a", "b"], "properties": {}}
        errs = cv.validate({"a": 1}, schema)
        self.assertEqual(len(errs), 1)
        self.assertIn("b", errs[0])
        self.assertEqual(len(cv.validate({}, schema)), 2)
        self.assertEqual(cv.validate({"a": 1, "b": 2}, schema), [])

    def test_types(self):
        good = {"string": "x", "integer": 3, "number": 1.5, "boolean": True,
                "array": [1], "object": {}}
        bad = {"string": 1, "integer": "3", "number": "1", "boolean": 0,
               "array": {}, "object": []}
        for t in good:
            schema = {"properties": {"v": {"type": t}}}
            self.assertEqual(cv.validate({"v": good[t]}, schema), [], t)
            errs = cv.validate({"v": bad[t]}, schema)
            self.assertEqual(len(errs), 1, t)
            self.assertTrue(errs[0].startswith("v:"), t)
        schema = {"properties": {"v": {"type": "integer"}}}
        self.assertEqual(len(cv.validate({"v": True}, schema)), 1)
        self.assertEqual(len(cv.validate({"v": 3.5}, schema)), 1)
        schema = {"properties": {"v": {"type": "number"}}}
        self.assertEqual(len(cv.validate({"v": True}, schema)), 1)
        self.assertEqual(cv.validate({"v": 3}, schema), [])

    def test_enum(self):
        schema = {"properties": {"m": {"enum": ["dev", "prod"]}}}
        self.assertEqual(cv.validate({"m": "dev"}, schema), [])
        self.assertEqual(len(cv.validate({"m": "test"}, schema)), 1)
        schema = {"properties": {"m": {"enum": [1, 2]}}}
        self.assertEqual(len(cv.validate({"m": True}, schema)), 1)

    def test_number_bounds(self):
        schema = {"properties": {"n": {"minimum": 1, "maximum": 10}}}
        self.assertEqual(cv.validate({"n": 1}, schema), [])
        self.assertEqual(cv.validate({"n": 10}, schema), [])
        self.assertIn("minimum", cv.validate({"n": 0}, schema)[0])
        self.assertIn("maximum", cv.validate({"n": 11}, schema)[0])
        self.assertEqual(cv.validate({"n": "zzz"}, schema), [])

    def test_string_length(self):
        schema = {"properties": {"s": {"minLength": 2, "maxLength": 4}}}
        self.assertEqual(cv.validate({"s": "ab"}, schema), [])
        self.assertEqual(cv.validate({"s": "abcd"}, schema), [])
        self.assertIn("minLength", cv.validate({"s": "a"}, schema)[0])
        self.assertIn("maxLength", cv.validate({"s": "abcde"}, schema)[0])

    def test_pattern(self):
        schema = {"properties": {"s": {"pattern": "^[a-z]+$"}}}
        self.assertEqual(cv.validate({"s": "abc"}, schema), [])
        errs = cv.validate({"s": "ABC"}, schema)
        self.assertEqual(len(errs), 1)
        self.assertIn("pattern", errs[0])
        unanchored = {"properties": {"s": {"pattern": "b"}}}
        self.assertEqual(cv.validate({"s": "abc"}, unanchored), [])

    def test_nested_paths(self):
        schema = {"required": ["server"], "properties": {"server": {
            "type": "object", "required": ["host"],
            "properties": {"port": {"type": "integer", "maximum": 65535},
                           "tls": {"type": "object", "required": ["cert"]}}}}}
        errs = cv.validate({"server": {"port": 70000, "tls": {}}}, schema)
        text = "\n".join(errs)
        self.assertIn("server.host: required", text)
        self.assertIn("server.port:", text)
        self.assertIn("server.tls.cert: required", text)
        self.assertEqual(len(errs), 3)
        self.assertIn("server: required", cv.validate({}, schema)[0])


class CliTests(unittest.TestCase):
    def _run(self, config, schema):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for name, content in (("c.json", config), ("s.json", schema)):
                p = os.path.join(d, name)
                with open(p, "w") as fh:
                    fh.write(content if isinstance(content, str) else json.dumps(content))
                paths.append(p)
            return self._main(paths)

    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cv.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_all_errors_and_exit_codes(self):
        schema = {"required": ["name", "port"], "properties": {
            "name": {"type": "string", "minLength": 3},
            "port": {"type": "integer", "minimum": 1},
            "db": {"type": "object", "properties": {"mode": {"enum": ["a"]}}}}}
        code, out, _ = self._run({"name": "x", "db": {"mode": "z"}}, schema)
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(any(l.startswith("db.mode:") for l in lines))
        code, out, _ = self._run({"name": "abc", "port": 5}, schema)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(self._run("{bad", schema)[0], 2)
        self.assertEqual(self._main(["/nonexistent/a", "/nonexistent/b"])[0], 2)
        self.assertEqual(self._main([])[0], 2)

    def test_stdlib_only(self):
        path = os.path.join(os.path.dirname(os.path.abspath(cv.__file__)), "config_validator.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        self.assertLessEqual(mods, {"json", "re", "sys"})


if __name__ == "__main__":
    unittest.main()
