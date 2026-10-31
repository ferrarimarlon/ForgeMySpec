import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scheduler.py")


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name
        self.state = os.path.join(self.cwd, "scheduler.json")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", SCRIPT, *args], cwd=self.cwd,
                              capture_output=True, text=True)

    def add(self, jid, prio=5, deps=""):
        return self.run_cli("add", "--id", jid, "--name", "n" + jid,
                            "--priority", str(prio), "--depends-on", deps)

    def jobs(self):
        with open(self.state) as fh:
            return {j["id"]: j for j in json.load(fh)["jobs"]}

    def raw(self):
        with open(self.state) as fh:
            return fh.read()

    def test_id_and_priority_format(self):
        self.assertEqual(self.add("a_1Z", 1).returncode, 0)
        self.assertEqual(self.add("x" * 32, 10).returncode, 0)
        before = self.raw()
        for bad in ("", "x" * 33, "a-b", "a b", "é", "a\n"):
            self.assertEqual(self.add(bad).returncode, 1, bad)
        for bad in (0, 11, -1, "abc", "1.5"):
            self.assertEqual(self.add("p", bad).returncode, 1, bad)
        self.assertEqual(self.raw(), before)

    def test_add_rejections(self):
        self.assertEqual(self.add("a").returncode, 0)
        before = self.raw()
        for r in (self.add("a"), self.add("b", deps="b"), self.add("c", deps="nope"),
                  self.add("d", deps="a,nope")):
            self.assertEqual(r.returncode, 1)
            self.assertIn("error", r.stderr)
        self.assertEqual(self.raw(), before)

    def test_cycle_rejected(self):
        # hand-written file: a depends on c, which does not exist yet
        with open(self.state, "w") as fh:
            json.dump({"jobs": [{"id": "a", "name": "A", "priority": 5,
                                 "depends_on": ["c"], "status": "pending"}]}, fh)
        before = self.raw()
        r = self.add("c", deps="a")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cycle", r.stderr)
        self.assertEqual(self.raw(), before)
        sys.path.insert(0, ROOT)
        try:
            import scheduler
        finally:
            sys.path.remove(ROOT)
        jobs = [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["c"]}]
        self.assertTrue(scheduler.find_cycle(jobs, "c", ["a"]))
        self.assertFalse(scheduler.find_cycle(jobs, "d", ["a", "b"]))

    def test_execution_order(self):
        self.add("low", 1)
        self.add("mid", 5, "low")
        self.add("hi", 10, "mid")
        self.add("other", 3)
        self.add("alpha", 3)
        r = self.run_cli("report")
        self.assertEqual(r.returncode, 0)
        lines = [l.split()[1] for l in r.stdout.splitlines() if l[:3].strip().rstrip(".").isdigit()]
        # roots: low(1), other(3), alpha(3) -> other/alpha first (alpha before other by id), then low,
        # mid and hi only after their prerequisites
        self.assertEqual(lines, ["alpha", "other", "low", "mid", "hi"])

    def test_ready_derived_not_persisted(self):
        self.add("a")
        self.add("b", deps="a")
        self.assertIn("ready", self.run_cli("status").stdout.splitlines()[0])
        self.assertNotIn("ready", self.raw())
        self.run_cli("run-next")
        self.assertNotIn('"ready"', self.raw())
        status = {l.split()[0]: l.split()[1] for l in self.run_cli("status").stdout.splitlines()}
        self.assertEqual(status, {"a": "done", "b": "ready"})
        # a file claiming ready is recomputed on load
        data = json.loads(self.raw())
        data["jobs"][1]["status"] = "ready"
        data["jobs"][0]["status"] = "pending"
        with open(self.state, "w") as fh:
            json.dump(data, fh)
        status = {l.split()[0]: l.split()[1] for l in self.run_cli("status").stdout.splitlines()}
        self.assertEqual(status, {"a": "ready", "b": "pending"})

    def test_failure_propagation(self):
        self.add("a")
        self.add("b", deps="a")
        self.add("c", deps="b")
        self.add("e")
        self.add("f", deps="e")
        r = self.run_cli("fail", "a")
        self.assertEqual(r.returncode, 0)
        st = {k: v["status"] for k, v in self.jobs().items()}
        self.assertEqual(st, {"a": "failed", "b": "cancelled", "c": "cancelled",
                              "e": "pending", "f": "pending"})
        self.assertEqual(self.run_cli("fail", "a").returncode, 1)
        self.assertEqual(self.run_cli("fail", "zzz").returncode, 1)
        self.assertEqual(self.run_cli("fail", "b").returncode, 1)

    def test_run_next(self):
        self.add("lo", 2)
        self.add("hi", 9)
        self.add("dep", 10, "lo")
        r = self.run_cli("run-next")
        self.assertEqual(r.returncode, 0)
        self.assertIn("running hi", r.stdout)
        self.assertIn("done hi", r.stdout)
        st = {k: v["status"] for k, v in self.jobs().items()}
        self.assertEqual(st, {"lo": "pending", "hi": "done", "dep": "pending"})
        self.run_cli("run-next")
        r = self.run_cli("run-next")  # dep (10) now ready
        self.assertIn("done dep", r.stdout)
        r = self.run_cli("run-next")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no ready job", r.stdout)

    def test_cli_commands(self):
        self.assertEqual(self.run_cli("status").returncode, 0)
        self.assertEqual(self.run_cli("bogus").returncode, 2)
        self.add("a", 4)
        self.add("b", 6, "a")
        r = self.run_cli("report")
        self.assertEqual(r.returncode, 0)
        self.assertIn("total     2", r.stdout)
        self.assertTrue(os.path.exists(self.state))
        self.assertEqual(self.run_cli("fail", "a").returncode, 0)
        self.assertIn("cancelled", self.run_cli("status").stdout)
        with open(self.state, "w") as fh:
            fh.write("{not json")
        self.assertEqual(self.run_cli("status").returncode, 1)


if __name__ == "__main__":
    unittest.main()
