import contextlib
import io
import json
import os
import tempfile
import unittest

import config_validator as cv


class ValidatorTests(unittest.TestCase):
    def test_required_missing(self):
        schema = {"type": "object", "required": ["a", "db"],
                  "properties": {"db": {"type": "object", "required": ["host"]}}}
        self.assertEqual(cv.validate({"db": {}}, schema),
                         ["a: required field missing", "db.host: required field missing"])
        self.assertEqual(cv.validate({"a": 1, "db": {"host": "x"}}, schema), [])

    def test_types(self):
        good = {"string": "s", "integer": 1, "number": 1.5, "boolean": True,
                "array": [], "object": {}}
        for t, v in good.items():
            self.assertEqual(cv.validate(v, {"type": t}), [], t)
        self.assertEqual(cv.validate(2, {"type": "number"}), [])
        bad = {"string": 1, "integer": 1.5, "number": "1", "boolean": 0,
               "array": {}, "object": []}
        for t, v in bad.items():
            self.assertEqual(len(cv.validate(v, {"type": t})), 1, t)
        self.assertEqual(len(cv.validate(True, {"type": "integer"})), 1)
        self.assertEqual(len(cv.validate(True, {"type": "number"})), 1)

    def test_enum(self):
        s = {"type": "string", "enum": ["a", "b"]}
        self.assertEqual(cv.validate("a", s), [])
        self.assertEqual(len(cv.validate("c", s)), 1)

    def test_number_bounds(self):
        s = {"type": "integer", "minimum": 1, "maximum": 10}
        self.assertEqual(cv.validate(1, s), [])
        self.assertEqual(cv.validate(10, s), [])
        self.assertIn("minimum", cv.validate(0, s)[0])
        self.assertIn("maximum", cv.validate(11, s)[0])

    def test_string_length(self):
        s = {"type": "string", "minLength": 2, "maxLength": 3}
        self.assertEqual(cv.validate("ab", s), [])
        self.assertEqual(cv.validate("abc", s), [])
        self.assertIn("minLength", cv.validate("a", s)[0])
        self.assertIn("maxLength", cv.validate("abcd", s)[0])

    def test_pattern(self):
        s = {"type": "string", "pattern": "^[a-z]+$"}
        self.assertEqual(cv.validate("abc", s), [])
        self.assertIn("pattern", cv.validate("ab1", s)[0])
        self.assertEqual(cv.validate("xx-abc", {"pattern": "abc"}), [])

    def test_nested_paths(self):
        schema = {"type": "object", "properties": {"db": {"type": "object", "properties": {
            "port": {"type": "integer", "maximum": 65535},
            "tls": {"type": "object", "properties": {"mode": {"enum": ["on", "off"]}}}}}}}
        errs = cv.validate({"db": {"port": 70000, "tls": {"mode": "x"}}}, schema)
        self.assertEqual(len(errs), 2)
        self.assertTrue(errs[0].startswith("db.port:"))
        self.assertTrue(errs[1].startswith("db.tls.mode:"))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, content):
        p = os.path.join(self.dir.name, name)
        with open(p, "w") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))
        return p

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cv.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_all_errors_at_once(self):
        schema = self.write("s.json", {"type": "object", "required": ["name", "mode"], "properties": {
            "port": {"type": "integer", "minimum": 1},
            "db": {"type": "object", "properties": {"user": {"type": "string", "minLength": 3}}}}})
        bad = self.write("c.json", {"port": 0, "db": {"user": "x"}})
        code, out, _ = self.run_cli([schema, bad])
        self.assertEqual(code, 1)
        self.assertEqual(len(out.strip().splitlines()), 4)
        good = self.write("g.json", {"name": "n", "mode": "m", "port": 5})
        self.assertEqual(self.run_cli([schema, good])[0], 0)

    def test_io_errors(self):
        schema = self.write("s.json", {"type": "object"})
        broken = self.write("b.json", "{not json")
        for args in ([], [schema], [schema, os.path.join(self.dir.name, "none.json")],
                     [schema, broken], [broken, schema]):
            code, out, err = self.run_cli(args)
            self.assertEqual(code, 2, args)
            self.assertTrue(err.startswith("error:"))
            self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
