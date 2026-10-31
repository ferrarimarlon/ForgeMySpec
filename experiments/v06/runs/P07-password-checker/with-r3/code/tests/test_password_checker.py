import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import password_checker as pc

STRICT = {"min_length": 8, "require_uppercase": True, "require_lowercase": True,
          "require_digits": True, "require_symbols": True,
          "forbidden_passwords": ["Password1!"]}


def run(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pc.main(argv)
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


def write_policy(d, policy, name="policy.json"):
    path = os.path.join(d, name)
    with open(path, "w") as fh:
        json.dump(policy, fh)
    return path


class CheckTests(unittest.TestCase):
    def test_reports_every_failed_rule(self):
        self.assertEqual(pc.check_password("abc", STRICT),
                         ["min_length", "uppercase", "digits", "symbols"])
        self.assertEqual(pc.check_password("", STRICT),
                         ["min_length", "uppercase", "lowercase", "digits", "symbols"])
        self.assertEqual(pc.check_password("password1!", STRICT), ["uppercase", "forbidden"])
        pol = {**STRICT, "forbidden_passwords": ["password1!"]}
        self.assertEqual(pc.check_password("PASSWORD1!", pol), ["lowercase", "forbidden"])
        self.assertEqual(pc.check_password("Passw0rd!x", STRICT), [])

    def test_cli_lists_all_failures_without_echo(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_policy(d, STRICT)
            code, out, _ = run(["check", "zq", "--policy", p])
        self.assertEqual(code, 1)
        for rule in ("min_length", "uppercase", "digits", "symbols"):
            self.assertIn(rule, out)
        self.assertNotIn("zq", out)

    def test_forbidden_case_insensitive(self):
        self.assertIn("forbidden", pc.check_password("PASSWORD1!", STRICT))


class EntropyTests(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(pc.shannon_entropy(""), 0.0)
        self.assertEqual(pc.shannon_entropy("aaaa"), 0.0)
        self.assertAlmostEqual(pc.shannon_entropy("abcd"), 8.0)
        self.assertAlmostEqual(pc.shannon_entropy("aabb"), 4.0)

    def test_cli_prints_entropy(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_policy(d, {"min_length": 1})
            _, out, _ = run(["check", "abcd", "--policy", p])
        self.assertIn("entropy: 8.00 bits", out)


class GenerateTests(unittest.TestCase):
    def test_generated_passwords_pass_policy(self):
        policies = [STRICT, pc.DEFAULT_POLICY,
                    {"min_length": 4, "require_uppercase": True, "require_lowercase": True,
                     "require_digits": True, "require_symbols": True},
                    {"min_length": 6, "require_digits": True},
                    {"min_length": 1}]
        for policy in policies:
            for _ in range(200):
                pw = pc.generate_password(policy)
                self.assertEqual(pc.check_password(pw, policy), [], pw)
                self.assertGreaterEqual(len(pw), policy["min_length"])

    def test_length_and_count(self):
        code, out, _ = run(["generate", "--length", "20", "--count", "3"])
        self.assertEqual(code, 0)
        lines = out.split()
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(x) == 20 for x in lines))
        self.assertEqual(run(["generate", "--length", "3"])[0], 2)

    def test_passwords_differ(self):
        self.assertGreater(len({pc.generate_password(STRICT) for _ in range(20)}), 1)


class PolicyTests(unittest.TestCase):
    def test_loads_policy_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_policy(d, STRICT)
            self.assertEqual(pc.load_policy(p), STRICT)
            old = os.getcwd()
            os.chdir(d)
            try:
                self.assertEqual(pc.load_policy(), STRICT)
                self.assertEqual(run(["check", "Passw0rd!x"])[0], 0)
            finally:
                os.chdir(old)
            broken = os.path.join(d, "broken.json")
            with open(broken, "w") as fh:
                fh.write("{not json")
            self.assertEqual(run(["check", "x", "--policy", broken])[0], 2)
            self.assertEqual(run(["check", "x", "--policy", os.path.join(d, "none.json")])[0], 2)

    def test_default_policy_when_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd()
            os.chdir(d)
            try:
                self.assertEqual(pc.load_policy(), pc.DEFAULT_POLICY)
            finally:
                os.chdir(old)

    def test_validate_policy_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            ok = write_policy(d, STRICT)
            self.assertEqual(run(["validate-policy", "--policy", ok])[0], 0)
            cases = {
                "min_length": {**STRICT, "min_length": 0},
                "require_digits": {**STRICT, "require_digits": "yes"},
                "forbidden_passwords": {**STRICT, "forbidden_passwords": "x"},
                "bogus": {**STRICT, "bogus": 1},
                "smaller": {**STRICT, "min_length": 3},
            }
            for field, pol in cases.items():
                p = write_policy(d, pol)
                code, _, err = run(["validate-policy", "--policy", p])
                self.assertEqual(code, 2, field)
                self.assertIn("min_length" if field == "smaller" else field, err)
            self.assertEqual(run(["validate-policy", "--policy", os.path.join(d, "x.json")])[0], 2)
            p = write_policy(d, [1, 2])
            self.assertEqual(run(["validate-policy", "--policy", p])[0], 2)


class CliTests(unittest.TestCase):
    def test_subcommands_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_policy(d, STRICT)
            self.assertEqual(run(["check", "Passw0rd!x", "--policy", p])[0], 0)
            self.assertEqual(run(["check", "weak", "--policy", p])[0], 1)
            self.assertEqual(run(["check", "--policy", p], stdin="Passw0rd!x\n")[0], 0)
            self.assertEqual(run(["generate", "--policy", p])[0], 0)
            self.assertEqual(run(["validate-policy", "--policy", p])[0], 0)
        self.assertEqual(run(["bogus"])[0], 2)
        self.assertEqual(run([])[0], 2)


class StructureTests(unittest.TestCase):
    def test_only_stdlib_imports(self):
        path = pc.__file__
        self.assertEqual(os.path.basename(path), "password_checker.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        self.assertLessEqual(mods, {"argparse", "json", "math", "secrets", "string", "sys", "collections"})


if __name__ == "__main__":
    unittest.main()
