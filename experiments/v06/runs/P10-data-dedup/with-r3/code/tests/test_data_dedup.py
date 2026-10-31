import ast
import contextlib
import io
import os
import sys
import tempfile
import unittest

import data_dedup

SAMPLE = "id,region,val\n1,eu,a\n2,eu,b\n1,us,c\n1,eu,d\n2,eu,e\n"


class DedupTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.src = os.path.join(self.d.name, "source.csv")
        self.out = os.path.join(self.d.name, "result.csv")
        with open(self.src, "w") as f:
            f.write(SAMPLE)

    def run_cli(self, *args):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            try:
                code = data_dedup.main(list(args))
            except SystemExit as x:
                code = x.code
        return code, o.getvalue(), e.getvalue()

    def read_out(self):
        with open(self.out) as f:
            return f.read().splitlines()

    def test_composite_key(self):
        code, _, _ = self.run_cli(self.src, "-k", "id,region", "-o", self.out)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_out(), ["id,region,val", "1,eu,a", "2,eu,b", "1,us,c"])
        self.run_cli(self.src, "-k", "id", "-o", self.out)
        self.assertEqual(self.read_out(), ["id,region,val", "1,eu,a", "2,eu,b"])

    def test_keep_first(self):
        self.run_cli(self.src, "-k", "id,region", "-s", "first", "-o", self.out)
        self.assertIn("1,eu,a", self.read_out())
        self.assertNotIn("1,eu,d", self.read_out())

    def test_keep_last(self):
        self.run_cli(self.src, "-k", "id,region", "-s", "last", "-o", self.out)
        self.assertEqual(self.read_out(), ["id,region,val", "1,us,c", "1,eu,d", "2,eu,e"])

    def test_output_csv_written(self):
        code, _, _ = self.run_cli(self.src, "-k", "id", "-o", self.out)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_out()[0], "id,region,val")

    def test_error_strategy_exits_nonzero(self):
        code, _, err = self.run_cli(self.src, "-k", "id,region", "-s", "error", "-o", self.out)
        self.assertEqual(code, 1)
        self.assertIn("eu", err)
        self.assertFalse(os.path.exists(self.out))
        code, _, _ = self.run_cli(self.src, "-k", "id,region,val", "-s", "error", "-o", self.out)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(self.out))

    def test_summary(self):
        _, out, _ = self.run_cli(self.src, "-k", "id,region", "-o", self.out)
        self.assertIn("Duplicates found: 2", out)
        self.assertIn("removed: 2", out)

    def test_missing_column_exits_2(self):
        code, _, err = self.run_cli(self.src, "-k", "nope", "-o", self.out)
        self.assertEqual(code, 2)
        self.assertIn("nope", err)
        code, _, err = self.run_cli(self.src + ".missing", "-k", "id", "-o", self.out)
        self.assertEqual(code, 2)
        self.assertTrue(err)

    def test_stdlib_only(self):
        with open(data_dedup.__file__) as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        self.assertTrue(mods <= {"argparse", "csv", "sys"}, mods)


if __name__ == "__main__":
    unittest.main()
