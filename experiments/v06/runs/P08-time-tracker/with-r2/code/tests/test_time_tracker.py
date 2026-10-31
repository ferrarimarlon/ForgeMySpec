import ast
import io
import os
import tempfile
import unittest
from datetime import datetime

import time_tracker as tt


def T(h, m=0, s=0, day=1):
    return datetime(2026, 1, day, h, m, s)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "t.json")

    def run_cmd(self, now, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = tt.main(["--file", self.path] + list(argv), now=now, out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def test_start_stop_persists(self):
        self.assertEqual(self.run_cmd(T(9), "start", "alpha")[0], 0)
        self.assertEqual(self.run_cmd(T(10, 30), "stop")[0], 0)
        s = tt.load(self.path)
        self.assertEqual(s, [{"project": "alpha", "start": "2026-01-01T09:00:00", "end": "2026-01-01T10:30:00"}])

    def test_start_refused_when_active(self):
        self.run_cmd(T(9), "start", "alpha")
        before = open(self.path, "rb").read()
        code, _, err = self.run_cmd(T(9, 5), "start", "beta")
        self.assertEqual(code, 1)
        self.assertIn("already active", err)
        self.assertEqual(open(self.path, "rb").read(), before)

    def test_overlap_detected(self):
        tt.save(self.path, [
            {"project": "a", "start": "2026-01-01T09:00:00", "end": "2026-01-01T10:00:00"},
            {"project": "b", "start": "2026-01-01T09:30:00", "end": "2026-01-01T11:00:00"},
            {"project": "c", "start": "2026-01-01T11:00:00", "end": "2026-01-01T12:00:00"},
        ])
        code, out, _ = self.run_cmd(T(13), "log")
        lines = out.splitlines()
        self.assertTrue(lines[0].endswith("OVERLAP"))
        self.assertTrue(lines[1].endswith("OVERLAP"))
        self.assertFalse(lines[2].endswith("OVERLAP"))
        self.assertIn("warning", out)

    def test_duration_format(self):
        self.assertEqual(tt.format_duration(0), "00:00:00")
        self.assertEqual(tt.format_duration(3661), "01:01:01")
        self.assertEqual(tt.format_duration(100 * 3600 + 5), "100:00:05")
        self.run_cmd(T(9), "start", "a")
        _, out, _ = self.run_cmd(T(9, 0, 7), "stop")
        self.assertIn("00:00:07", out)

    def test_report_totals(self):
        tt.save(self.path, [
            {"project": "a", "start": "2026-01-01T09:00:00", "end": "2026-01-01T10:00:00"},
            {"project": "b", "start": "2026-01-01T10:00:00", "end": "2026-01-01T10:10:00"},
            {"project": "a", "start": "2026-01-01T11:00:00", "end": "2026-01-01T11:30:30"},
        ])
        _, out, _ = self.run_cmd(T(13), "report")
        self.assertEqual(out.splitlines(), ["a  01:30:30", "b  00:10:00"])

    def test_stdlib_only(self):
        tree = ast.parse(open(tt.__file__).read())
        allowed = {"argparse", "json", "os", "sys", "datetime"}
        for n in ast.walk(tree):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                [n.module] if isinstance(n, ast.ImportFrom) else []
            for name in names:
                self.assertIn(name.split(".")[0], allowed)

    def test_stop_without_active(self):
        self.assertEqual(self.run_cmd(T(9), "stop")[0], 1)


if __name__ == "__main__":
    unittest.main()
