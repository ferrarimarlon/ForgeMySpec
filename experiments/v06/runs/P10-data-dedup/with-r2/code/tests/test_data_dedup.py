import ast
import contextlib
import csv
import io
import os
import tempfile
import unittest

import data_dedup

HEADER = ["id", "region", "val"]
ROWS = [
    ["1", "eu", "a"],
    ["2", "eu", "b"],
    ["1", "us", "c"],
    ["1", "eu", "d"],
    ["2", "eu", "e"],
]


class DedupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inp = os.path.join(self.tmp.name, "in.csv")
        self.out = os.path.join(self.tmp.name, "out.csv")
        with open(self.inp, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            w.writerows(ROWS)

    def cli(self, *argv):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            try:
                code = data_dedup.main(list(argv))
            except SystemExit as x:
                code = x.code
        return code, o.getvalue(), e.getvalue()

    def read_out(self):
        with open(self.out, newline="") as f:
            return list(csv.reader(f))

    def test_composite_key(self):
        code, _, _ = self.cli(self.inp, self.out, "-k", "id", "region")
        self.assertEqual(code, 0)
        # (1,us) differs from (1,eu) so it is kept
        self.assertEqual(self.read_out()[1:], [ROWS[0], ROWS[1], ROWS[2]])
        self.cli(self.inp, self.out, "-k", "id")
        self.assertEqual(len(self.read_out()), 3)  # header + ids 1, 2

    def test_keep_first(self):
        self.cli(self.inp, self.out, "-k", "id", "region", "-s", "first")
        self.assertEqual(self.read_out()[1:], [ROWS[0], ROWS[1], ROWS[2]])

    def test_keep_last(self):
        self.cli(self.inp, self.out, "-k", "id", "region", "-s", "last")
        self.assertEqual(self.read_out()[1:], [ROWS[2], ROWS[3], ROWS[4]])

    def test_error_strategy_exits_nonzero(self):
        code, _, err = self.cli(self.inp, self.out, "-k", "id", "region", "-s", "error")
        self.assertNotEqual(code, 0)
        self.assertIn("rows 1, 4", err)
        self.assertIn("rows 2, 5", err)
        self.assertFalse(os.path.exists(self.out))

    def test_error_strategy_no_duplicates(self):
        code, out, _ = self.cli(self.inp, self.out, "-k", "id", "region", "val", "-s", "error")
        self.assertEqual(code, 0)
        self.assertIn("found: 0, removed: 0", out)
        self.assertEqual(len(self.read_out()), 6)

    def test_output_csv(self):
        self.cli(self.inp, self.out, "-k", "id")
        rows = self.read_out()
        self.assertEqual(rows[0], HEADER)
        self.assertEqual(rows[1:], [ROWS[0], ROWS[1]])

    def test_summary(self):
        _, out, _ = self.cli(self.inp, self.out, "-k", "id", "region")
        self.assertIn("Duplicates found: 2, removed: 2", out)
        _, out, _ = self.cli(self.inp, self.out, "-k", "id", "region", "-s", "error")
        self.assertIn("Duplicates found: 2, removed: 0", out)

    def test_missing_column(self):
        code, _, err = self.cli(self.inp, self.out, "-k", "id", "nope")
        self.assertNotEqual(code, 0)
        self.assertIn("nope", err)
        self.assertFalse(os.path.exists(self.out))
        code, _, _ = self.cli(os.path.join(self.tmp.name, "absent.csv"), self.out, "-k", "id")
        self.assertNotEqual(code, 0)

    def test_stdlib_only(self):
        import importlib.util
        import sysconfig
        path = data_dedup.__file__
        with open(path) as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        self.assertTrue(mods)
        stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
        for m in mods:
            spec = importlib.util.find_spec(m)
            self.assertIsNotNone(spec, m)
            origin = spec.origin
            if origin in ("built-in", "frozen"):
                continue
            origin = os.path.realpath(origin)
            self.assertTrue(origin.startswith(stdlib + os.sep), m)
            self.assertNotIn("site-packages", origin, m)


if __name__ == "__main__":
    unittest.main()
