import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import password_checker as pc

STRICT = {
    "min_length": 12, "require_uppercase": True, "require_lowercase": True,
    "require_digits": True, "require_symbols": True, "forbidden_passwords": ["Password1!x"],
}


def run(argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pc.main(argv)
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class TmpPolicy(unittest.TestCase):
    def policy_file(self, data, raw=None):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = os.path.join(d.name, "policy.json")
        with open(path, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(data))
        return path


class CheckTests(TmpPolicy):
    def test_reports_every_failed_rule(self):
        pol = self.policy_file(dict(STRICT, forbidden_passwords=["abc"]))
        code, out, _ = run(["check", "--password", "abc", "--policy", pol])
        self.assertEqual(code, 1)
        self.assertEqual(out.count("  - "), 5)
        for word in ("length", "uppercase", "digit", "symbol", "forbidden"):
            self.assertIn(word, out)
        self.assertIn("bits", out)
        code, out, _ = run(["check", "--policy", pol], stdin="Tr0ub4dor&3xyz\n")
        self.assertEqual(code, 0)
        code, out, _ = run(["check", "--password", "PASSWORD1!X", "--policy",
                            self.policy_file(dict(STRICT, forbidden_passwords=["password1!x"]))])
        self.assertEqual(code, 1)
        self.assertIn("lowercase", out)
        self.assertIn("forbidden", out)


class EntropyTests(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(pc.entropy_bits(""), 0.0)
        self.assertEqual(pc.entropy_bits("aaaa"), 0.0)
        self.assertAlmostEqual(pc.entropy_bits("abcd"), 8.0)
        self.assertAlmostEqual(pc.entropy_bits("aabb"), 4.0)


class GenerateTests(TmpPolicy):
    def test_generated_pass_check(self):
        pol = pc.load_policy(self.policy_file(STRICT))
        for _ in range(200):
            pw = pc.generate_password(pol)
            self.assertEqual(pc.failed_rules(pw, pol), [])
        path = self.policy_file(STRICT)
        code, out, _ = run(["generate", "--policy", path, "--length", "12", "--count", "5"])
        self.assertEqual(code, 0)
        lines = out.split()
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(len(x) == 12 for x in lines))
        self.assertEqual(run(["generate", "--policy", path, "--length", "11"])[0], 2)
        loose = self.policy_file({"min_length": 1})
        self.assertEqual(run(["generate", "--policy", loose, "--length", "1"])[0], 0)


class PolicyTests(TmpPolicy):
    def test_loads_policy_json(self):
        pol = pc.load_policy(self.policy_file({"min_length": 5}))
        self.assertEqual(pol["min_length"], 5)
        self.assertFalse(pol["require_digits"])
        self.assertEqual(pol["forbidden_passwords"], [])
        cwd = os.getcwd()
        d = os.path.dirname(self.policy_file({"min_length": 20}))
        os.chdir(d)
        try:
            code, out, _ = run(["check", "--password", "short"])
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 1)
        self.assertIn("minimum length 20", out)
        self.assertEqual(run(["check", "--password", "x", "--policy", "/nonexistent/p.json"])[0], 2)


class ValidatePolicyTests(TmpPolicy):
    def test_rejects_malformed(self):
        self.assertEqual(run(["validate-policy", "--policy", self.policy_file(STRICT)])[0], 0)
        bad = [
            ({"min_length": "8"}, "min_length"),
            ({"min_length": 0}, "min_length"),
            ({"min_length": True}, "min_length"),
            ({"require_digits": "yes"}, "require_digits"),
            ({"forbidden_passwords": "abc"}, "forbidden_passwords"),
            ({"colour": 1}, "unknown key"),
            ({"min_length": 2, "require_digits": True, "require_symbols": True,
              "require_uppercase": True}, "smaller"),
            ([1], "object"),
        ]
        for data, word in bad:
            code, _, err = run(["validate-policy", "--policy", self.policy_file(data)])
            self.assertEqual(code, 2, data)
            self.assertIn(word, err)
        code, _, err = run(["validate-policy", "--policy", self.policy_file(None, raw="{nope")])
        self.assertEqual(code, 2)
        self.assertIn("invalid JSON", err)


class CliTests(unittest.TestCase):
    def test_subcommands(self):
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run(["bogus"])[0], 2)
        parser = pc.build_parser()
        for cmd in ("check", "generate", "validate-policy"):
            self.assertIn(cmd, parser.format_help())

    def test_stdlib_only(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "password_checker.py")) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        allowed = {"argparse", "json", "math", "secrets", "string", "sys", "collections"}
        self.assertTrue(mods <= allowed, mods)
        py = [f for f in os.listdir(here) if f.endswith(".py")]
        self.assertEqual(py, ["password_checker.py"])


if __name__ == "__main__":
    unittest.main()
