import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

import config_validator as cv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "config_validator.py")


class ValidatorTests(unittest.TestCase):
    def test_required_missing(self):
        errs = cv.validate({"a": 1}, {"required": ["a", "b"]})
        self.assertEqual(len(errs), 1)
        self.assertIn("b", errs[0])
        self.assertIn("required", errs[0])

    def test_types(self):
        good = {"string": "x", "integer": 1, "number": 1.5, "boolean": True, "array": [], "object": {}}
        for t, v in good.items():
            self.assertEqual(cv.validate({"k": v}, {"properties": {"k": {"type": t}}}), [], t)
        bad = {"string": 1, "integer": 1.5, "number": "1", "boolean": 0, "array": {}, "object": []}
        for t, v in bad.items():
            errs = cv.validate({"k": v}, {"properties": {"k": {"type": t}}})
            self.assertEqual(len(errs), 1, t)
            self.assertTrue(errs[0].startswith("k:"))
        for t in ("integer", "number"):
            self.assertEqual(len(cv.validate({"k": True}, {"properties": {"k": {"type": t}}})), 1)

    def test_enum(self):
        s = {"properties": {"m": {"enum": ["a", "b"]}}}
        self.assertEqual(cv.validate({"m": "a"}, s), [])
        errs = cv.validate({"m": "c"}, s)
        self.assertEqual(len(errs), 1)
        self.assertIn("enum", errs[0])

    def test_number_bounds(self):
        s = {"properties": {"n": {"type": "number", "minimum": 1, "maximum": 10}}}
        self.assertEqual(cv.validate({"n": 1}, s), [])
        self.assertEqual(cv.validate({"n": 10}, s), [])
        self.assertIn("minimum", cv.validate({"n": 0}, s)[0])
        self.assertIn("maximum", cv.validate({"n": 11}, s)[0])

    def test_string_length(self):
        s = {"properties": {"s": {"type": "string", "minLength": 2, "maxLength": 4}}}
        self.assertEqual(cv.validate({"s": "ab"}, s), [])
        self.assertEqual(cv.validate({"s": "abcd"}, s), [])
        self.assertIn("minLength", cv.validate({"s": "a"}, s)[0])
        self.assertIn("maxLength", cv.validate({"s": "abcde"}, s)[0])

    def test_pattern(self):
        s = {"properties": {"s": {"type": "string", "pattern": "^[a-z]+$"}}}
        self.assertEqual(cv.validate({"s": "abc"}, s), [])
        errs = cv.validate({"s": "ab1"}, s)
        self.assertEqual(len(errs), 1)
        self.assertIn("pattern", errs[0])
        # re.search semantics
        self.assertEqual(cv.validate({"s": "xx7"}, {"properties": {"s": {"pattern": r"\d"}}}), [])

    def test_nested_paths(self):
        schema = {"properties": {"server": {"type": "object", "required": ["host"], "properties": {
            "tls": {"type": "object", "required": ["port"], "properties": {
                "port": {"type": "integer", "maximum": 65535}}}}}}}
        errs = cv.validate({"server": {"tls": {"port": 70000}}}, schema)
        self.assertEqual(len(errs), 2)
        self.assertTrue(any(e.startswith("server.host:") for e in errs))
        self.assertTrue(any(e.startswith("server.tls.port:") for e in errs))
        errs = cv.validate({"server": {"host": "h", "tls": {}}}, schema)
        self.assertEqual(errs, ["server.tls.port: required field is missing"])


class CliTests(unittest.TestCase):
    def _run(self, config, schema, raw=False):
        with tempfile.TemporaryDirectory() as d:
            cp, sp = os.path.join(d, "c.json"), os.path.join(d, "s.json")
            with open(cp, "w") as f:
                f.write(config if raw else json.dumps(config))
            with open(sp, "w") as f:
                f.write(json.dumps(schema))
            return subprocess.run([sys.executable, SCRIPT, cp, sp], capture_output=True, text=True)

    def test_reports_all_errors_and_exit_codes(self):
        schema = {"required": ["name", "mode"], "properties": {
            "port": {"type": "integer", "minimum": 1},
            "mode": {"enum": ["a", "b"]},
            "db": {"type": "object", "properties": {"user": {"type": "string", "minLength": 3}}}}}
        r = self._run({"port": 0, "mode": "z", "db": {"user": "x"}}, schema)
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 4)
        for prefix in ("name:", "port:", "mode:", "db.user:"):
            self.assertTrue(any(l.startswith(prefix) for l in lines), prefix)
        ok = self._run({"name": "n", "mode": "a"}, schema)
        self.assertEqual(ok.returncode, 0)
        self.assertEqual(self._run("{bad", schema, raw=True).returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, SCRIPT], capture_output=True).returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, SCRIPT, "/nope1", "/nope2"], capture_output=True).returncode, 2)

    def test_stdlib_only(self):
        with open(SCRIPT) as f:
            tree = ast.parse(f.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        self.assertTrue(mods)
        self.assertTrue(mods <= {"json", "re", "sys"}, mods)


if __name__ == "__main__":
    unittest.main()
