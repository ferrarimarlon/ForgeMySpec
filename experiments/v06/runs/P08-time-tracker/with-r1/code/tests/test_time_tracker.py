import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import time_tracker

T0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iso(dt):
    return dt.isoformat(timespec="seconds")


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "data.json")

    def run_cli(self, *args, now=T0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = time_tracker.main(["--file", self.path, *args], now=now)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def write(self, sessions):
        with open(self.path, "w") as fh:
            json.dump({"sessions": sessions}, fh)

    def read(self):
        with open(self.path) as fh:
            return json.load(fh)

    def test_start_refused_when_active(self):
        self.assertEqual(self.run_cli("start", "alpha")[0], 0)
        before = open(self.path).read()
        code, _, err = self.run_cli("start", "beta", now=T0 + timedelta(minutes=5))
        self.assertEqual(code, 1)
        self.assertIn("already active", err)
        self.assertEqual(open(self.path).read(), before)

    def test_start_stop_roundtrip(self):
        self.assertEqual(self.run_cli("stop")[0], 1)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.run_cli("start", "alpha")[0], 0)
        self.assertEqual(self.read()["sessions"],
                         [{"project": "alpha", "start": iso(T0), "end": None}])
        code, out, _ = self.run_cli("stop", now=T0 + timedelta(seconds=3725))
        self.assertEqual(code, 0)
        self.assertIn("01:02:05", out)
        self.assertEqual(self.read()["sessions"][0]["end"], iso(T0 + timedelta(seconds=3725)))
        self.assertEqual(self.run_cli("stop")[0], 1)
        # a new session may start once the previous one is closed
        self.assertEqual(self.run_cli("start", "beta", now=T0 + timedelta(hours=2))[0], 0)

    def test_json_persistence_and_corrupt_file(self):
        self.run_cli("start", "alpha")
        self.run_cli("stop", now=T0 + timedelta(minutes=1))
        self.run_cli("start", "beta", now=T0 + timedelta(minutes=2))
        self.assertEqual([s["project"] for s in self.read()["sessions"]], ["alpha", "beta"])
        code, out, _ = self.run_cli("log", now=T0 + timedelta(minutes=3))
        self.assertEqual(code, 0)
        self.assertIn("alpha", out)
        self.assertIn("(active)", out)
        for bad in ("{not json", "[]", '{"sessions": [{"project": "a", "start": "nope", "end": null}]}',
                    json.dumps({"sessions": [
                        {"project": "a", "start": iso(T0), "end": None},
                        {"project": "b", "start": iso(T0), "end": None}]})):
            with open(self.path, "w") as fh:
                fh.write(bad)
            for cmd in (("start", "x"), ("stop",), ("log",), ("report",)):
                code, _, err = self.run_cli(*cmd)
                self.assertEqual(code, 2, (bad, cmd))
                self.assertIn("error", err)
                self.assertEqual(open(self.path).read(), bad)

    def test_overlap_detected(self):
        self.write([
            {"project": "a", "start": iso(T0), "end": iso(T0 + timedelta(hours=2))},
            {"project": "b", "start": iso(T0 + timedelta(hours=1)), "end": iso(T0 + timedelta(hours=3))},
            {"project": "c", "start": iso(T0 + timedelta(hours=3)), "end": iso(T0 + timedelta(hours=4))},
        ])
        code, out, _ = self.run_cli("log", now=T0 + timedelta(hours=5))
        self.assertEqual(code, 0)
        lines = {l.split()[-2] if "[OVERLAP]" in l else l.split()[-1]: l for l in out.splitlines()[:3]}
        self.assertIn("[OVERLAP]", lines["a"])
        self.assertIn("[OVERLAP]", lines["b"])
        self.assertNotIn("[OVERLAP]", lines["c"])  # adjacent to b, no overlap
        self.assertIn("2 overlapping sessions detected", out)

    def test_overlap_with_active_session(self):
        self.write([
            {"project": "a", "start": iso(T0), "end": None},
            {"project": "b", "start": iso(T0 + timedelta(hours=1)), "end": iso(T0 + timedelta(hours=2))},
        ])
        _, out, _ = self.run_cli("log", now=T0 + timedelta(hours=3))
        self.assertEqual(out.count("[OVERLAP]"), 2)

    def test_no_overlap_means_no_warning(self):
        self.write([
            {"project": "a", "start": iso(T0), "end": iso(T0 + timedelta(hours=1))},
            {"project": "b", "start": iso(T0 + timedelta(hours=2)), "end": iso(T0 + timedelta(hours=3))},
        ])
        _, out, _ = self.run_cli("log")
        self.assertNotIn("OVERLAP", out)
        self.assertNotIn("overlapping", out)

    def test_duration_format(self):
        fmt = time_tracker.format_duration
        self.assertEqual(fmt(0), "00:00:00")
        self.assertEqual(fmt(59), "00:00:59")
        self.assertEqual(fmt(61), "00:01:01")
        self.assertEqual(fmt(3661), "01:01:01")
        self.assertEqual(fmt(100 * 3600 + 5), "100:00:05")
        self.assertEqual(fmt(-5), "00:00:00")
        self.write([{"project": "a", "start": iso(T0), "end": iso(T0 + timedelta(seconds=3661))}])
        self.assertIn("01:01:01", self.run_cli("log")[1])
        self.assertIn("01:01:01", self.run_cli("report")[1])

    def test_report_totals(self):
        self.write([
            {"project": "alpha", "start": iso(T0), "end": iso(T0 + timedelta(hours=1))},
            {"project": "beta", "start": iso(T0 + timedelta(hours=1)), "end": iso(T0 + timedelta(hours=1, minutes=30))},
            {"project": "alpha", "start": iso(T0 + timedelta(hours=2)), "end": iso(T0 + timedelta(hours=2, minutes=15))},
            {"project": "beta", "start": iso(T0 + timedelta(hours=3)), "end": None},
        ])
        code, out, _ = self.run_cli("report", now=T0 + timedelta(hours=3, minutes=10))
        self.assertEqual(code, 0)
        rows = {l.split()[0]: l.split()[1] for l in out.splitlines()}
        self.assertEqual(rows, {"alpha": "01:15:00", "beta": "00:40:00"})

    def test_empty_log_and_report(self):
        self.assertEqual(self.run_cli("log")[0], 0)
        self.assertEqual(self.run_cli("report")[0], 0)

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.run_cli()[0], 2)
        self.assertEqual(self.run_cli("start")[0], 2)
        self.assertEqual(self.run_cli("start", "  ")[0], 2)

    def test_stdlib_only(self):
        with open(os.path.join(ROOT, "time_tracker.py")) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:  # Python < 3.10: explicit allowlist of the stdlib modules the tool may use
            stdlib = {"argparse", "json", "os", "sys", "datetime"}
        self.assertLessEqual(mods, set(stdlib))
        py_files = [f for f in os.listdir(ROOT) if f.endswith(".py")]
        self.assertEqual(py_files, ["time_tracker.py"])


if __name__ == "__main__":
    unittest.main()
