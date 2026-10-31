import contextlib
import io
import os
import tempfile
import unittest

import data_dedup

SAMPLE = "id,region,v\n1,a,x\n1,b,y\n1,a,z\n2,a,w\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = data_dedup.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class DedupTests(unittest.TestCase):
    rows = [["1", "a", "x"], ["1", "b", "y"], ["1", "a", "z"], ["2", "a", "w"]]

    def test_composite_key(self):
        kept, dups = data_dedup.dedup(self.rows, [0, 1], "first")
        self.assertEqual(len(kept), 3)
        self.assertEqual(dups, {("1", "a"): 2})
        kept, _ = data_dedup.dedup(self.rows, [0], "first")
        self.assertEqual(len(kept), 2)

    def test_keep_first(self):
        kept, _ = data_dedup.dedup(self.rows, [0, 1], "first")
        self.assertEqual(kept, [self.rows[0], self.rows[1], self.rows[3]])

    def test_keep_last(self):
        kept, _ = data_dedup.dedup(self.rows, [0, 1], "last")
        self.assertEqual(kept, [self.rows[1], self.rows[2], self.rows[3]])


class CliTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.src = os.path.join(d.name, "source.csv")
        self.dst = os.path.join(d.name, "result.csv")
        with open(self.src, "w", newline="") as f:
            f.write(SAMPLE)

    def read_dst(self):
        with open(self.dst, newline="") as f:
            return f.read().replace("\r\n", "\n")

    def test_error_strategy_exits_nonzero(self):
        code, _, err = run([self.src, "-k", "id", "region", "-o", self.dst, "-s", "error"])
        self.assertEqual(code, 1)
        self.assertIn("duplicate key", err)
        self.assertFalse(os.path.exists(self.dst))
        code, _, _ = run([self.src, "-k", "id", "v", "-o", self.dst, "-s", "error"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(self.dst))

    def test_writes_output_csv(self):
        code, _, _ = run([self.src, "-k", "id", "region", "-o", self.dst, "-s", "last"])
        self.assertEqual(code, 0)
        self.assertEqual(self.read_dst(), "id,region,v\n1,b,y\n1,a,z\n2,a,w\n")

    def test_summary_counts(self):
        code, out, _ = run([self.src, "-k", "id", "-o", self.dst])
        self.assertEqual(code, 0)
        self.assertIn("duplicates found: 2, removed: 2", out)

    def test_unknown_column_exits_2(self):
        code, _, err = run([self.src, "-k", "nope", "-o", self.dst])
        self.assertEqual(code, 2)
        self.assertIn("nope", err)
        self.assertFalse(os.path.exists(self.dst))
        code, _, _ = run([self.src + ".missing", "-k", "id", "-o", self.dst])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(self.dst))


if __name__ == "__main__":
    unittest.main()
