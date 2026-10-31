import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime
from unittest import mock

import time_tracker as tt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dt(s):
    return datetime.strptime(s, tt.TS_FORMAT)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "data.json")

    def run_cli(self, *argv, at="2026-01-01T10:00:00"):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(tt, "now", return_value=dt(at)), redirect_stderr(err):
            code = tt.main(["--file", self.path, *argv], out)
        return code, out.getvalue(), err.getvalue()

    def write(self, sessions):
        with open(self.path, "w") as fh:
            json.dump({"sessions": sessions}, fh)

    def test_start_stop_persist(self):
        self.assertEqual(self.run_cli("start", "alpha")[0], 0)
        with open(self.path) as fh:
            d = json.load(fh)
        self.assertEqual(d["sessions"], [{"project": "alpha", "start": "2026-01-01T10:00:00", "end": None}])
        code, out, _ = self.run_cli("stop", at="2026-01-01T11:30:05")
        self.assertEqual(code, 0)
        self.assertIn("01:30:05", out)
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["sessions"][0]["end"], "2026-01-01T11:30:05")
        # survives a new process
        r = subprocess.run([sys.executable, os.path.join(ROOT, "time_tracker.py"),
                            "--file", self.path, "log"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("alpha", r.stdout)
        self.assertIn("01:30:05", r.stdout)

    def test_start_refused_when_active(self):
        self.run_cli("start", "alpha")
        with open(self.path) as fh:
            before = fh.read()
        code, _, err = self.run_cli("start", "beta", at="2026-01-01T10:05:00")
        self.assertNotEqual(code, 0)
        self.assertIn("alpha", err)
        with open(self.path) as fh:
            self.assertEqual(fh.read(), before)

    def test_overlap_detected(self):
        self.write([
            {"project": "a", "start": "2026-01-01T08:00:00", "end": "2026-01-01T09:00:00"},
            {"project": "b", "start": "2026-01-01T08:30:00", "end": "2026-01-01T09:30:00"},
            {"project": "c", "start": "2026-01-01T09:30:00", "end": "2026-01-01T10:00:00"},
        ])
        code, out, _ = self.run_cli("log")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("OVERLAP with #2", lines[0])
        self.assertIn("OVERLAP with #1", lines[1])
        self.assertNotIn("OVERLAP", lines[2])  # touching endpoints only

    def test_duration_format(self):
        self.assertEqual(tt.format_duration(0), "00:00:00")
        self.assertEqual(tt.format_duration(59), "00:00:59")
        self.assertEqual(tt.format_duration(3661), "01:01:01")
        self.assertEqual(tt.format_duration(90000), "25:00:00")
        self.assertEqual(tt.format_duration(360001), "100:00:01")

    def test_report_totals(self):
        self.write([
            {"project": "b", "start": "2026-01-01T08:00:00", "end": "2026-01-01T09:00:00"},
            {"project": "a", "start": "2026-01-01T09:00:00", "end": "2026-01-01T09:30:00"},
            {"project": "b", "start": "2026-01-01T09:30:00", "end": "2026-01-01T09:45:10"},
            {"project": "a", "start": "2026-01-01T09:50:00", "end": None},
        ])
        code, out, _ = self.run_cli("report", at="2026-01-01T10:00:00")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["a 00:40:00", "b 01:15:10"])

    def test_error_exits(self):
        code, _, err = self.run_cli("stop")
        self.assertNotEqual(code, 0)
        self.assertIn("no active session", err)
        for bad in ("{not json", '{"sessions": "x"}', '{"sessions": [{"project": "a"}]}'):
            with open(self.path, "w") as fh:
                fh.write(bad)
            for cmd in (["log"], ["report"], ["stop"], ["start", "x"]):
                code, _, err = self.run_cli(*cmd)
                self.assertNotEqual(code, 0)
                self.assertTrue(err.startswith("error:"))
            with open(self.path) as fh:
                self.assertEqual(fh.read(), bad)

    def test_stdlib_only(self):
        with open(os.path.join(ROOT, "time_tracker.py")) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                mods.add(n.module.split(".")[0])
        self.assertTrue(mods)
        stdlib = getattr(sys, "stdlib_module_names", None) or {
            "argparse", "json", "os", "sys", "tempfile", "datetime"}
        self.assertLessEqual(mods, set(stdlib))


if __name__ == "__main__":
    unittest.main()
