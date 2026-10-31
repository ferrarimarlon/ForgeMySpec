import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scheduler.py")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "scheduler.json")

    def run_cli(self, *args):
        env = dict(os.environ, SCHEDULER_FILE=self.path)
        return subprocess.run([sys.executable, SCRIPT, *args], env=env,
                              capture_output=True, text=True)

    def add(self, id_, priority=5, deps=(), name=None):
        cmd = ["add", "--id", id_, "--name", name or id_, "--priority", str(priority)]
        if deps:
            cmd += ["--depends-on", *deps]
        return self.run_cli(*cmd)

    def raw(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def statuses(self):
        out = self.run_cli("status").stdout.splitlines()
        return {line.split()[0]: line.split()[1] for line in out}

    def write_state(self, jobs):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"jobs": jobs}, fh)


def J(id_, status="pending", deps=(), priority=5):
    return {"id": id_, "name": id_, "priority": priority,
            "depends_on": list(deps), "status": status}


class ValidationTests(Base):
    def test_duplicate_id_rejected(self):
        self.assertEqual(self.add("a").returncode, 0)
        before = open(self.path).read()
        r = self.add("a", priority=9)
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicate", r.stderr)
        self.assertEqual(open(self.path).read(), before)

    def test_self_dependency_rejected(self):
        r = self.add("a", deps=["a"])
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.path))

    def test_unknown_dependency_rejected(self):
        r = self.add("a", deps=["ghost"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown dependency", r.stderr)
        self.assertFalse(os.path.exists(self.path))

    def test_id_format(self):
        for bad in ["", "a" * 33, "a-b", "a b", "a.b"]:
            self.assertEqual(self.add(bad).returncode, 1, bad)
        self.assertEqual(self.add("a" * 32).returncode, 0)
        self.assertEqual(self.add("Az_09").returncode, 0)

    def test_priority_range(self):
        for bad in ["0", "11", "x", "1.5", "-1"]:
            self.assertEqual(self.run_cli("add", "--id", "p", "--name", "n",
                                          "--priority", bad).returncode, 1, bad)
        self.assertEqual(self.add("lo", priority=1).returncode, 0)
        self.assertEqual(self.add("hi", priority=10).returncode, 0)


class CycleTests(Base):
    def test_cycle_rejected(self):
        # Via the CLI a new job can only depend on existing jobs, so a cycle
        # needs a self edge or a cyclic file; both must be refused.
        self.assertEqual(self.add("a", deps=["a"]).returncode, 1)
        self.write_state([J("a", deps=["b"]), J("b", deps=["a"])])
        before = open(self.path).read()
        r = self.add("c")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cycle", r.stderr)
        self.assertEqual(open(self.path).read(), before)

    def test_find_cycle_unit(self):
        sys.path.insert(0, ROOT)
        import scheduler
        jobs = {j["id"]: j for j in [J("a", deps=["c"]), J("b", deps=["a"]), J("c", deps=["b"])]}
        self.assertIsNotNone(scheduler.find_cycle(jobs))
        jobs = {j["id"]: j for j in [J("a"), J("b", deps=["a"]), J("c", deps=["a", "b"])]}
        self.assertIsNone(scheduler.find_cycle(jobs))
        with self.assertRaises(scheduler.SchedulerError):
            # a new job closing a loop through a pre-existing edge
            existing = {"x": J("x", deps=["y"]), "y": J("y")}
            existing["y"]["depends_on"] = ["x"]
            scheduler.add_job(existing, "z", "z", 1, ["x"])


class OrderTests(Base):
    def test_topological_with_priority_tiebreak(self):
        self.add("low_root", priority=1)
        self.add("mid_root", priority=5)
        self.add("urgent_child", priority=10, deps=["low_root"])
        self.add("high_root", priority=8)
        r = self.run_cli("report")
        self.assertEqual(r.returncode, 0)
        order = [l.split()[1] for l in r.stdout.split("Counts:")[0].splitlines()[1:]]
        self.assertEqual(order, ["high_root", "mid_root", "low_root", "urgent_child"])


class ReadyTests(Base):
    def test_ready_definition(self):
        self.add("a")
        self.add("b", deps=["a"])
        self.assertEqual(self.statuses(), {"a": "ready", "b": "pending"})
        self.run_cli("run-next")
        self.assertEqual(self.statuses(), {"a": "done", "b": "ready"})

    def test_ready_not_persisted(self):
        self.add("a")
        self.add("b", deps=["a"])
        self.assertNotIn("ready", open(self.path).read())
        self.run_cli("run-next")
        self.assertNotIn("ready", open(self.path).read())
        self.assertEqual({j["status"] for j in self.raw()["jobs"]}, {"done", "pending"})

    def test_ready_recomputed_on_load(self):
        self.write_state([J("a", "done"), J("b", "pending", ["a"]),
                          J("c", "pending", ["b"]), J("d", "ready", ["c"])])
        self.assertEqual(self.statuses(),
                         {"a": "done", "b": "ready", "c": "pending", "d": "pending"})


class FailTests(Base):
    def test_transitive_dependents_cancelled(self):
        self.add("root")
        self.add("mid", deps=["root"])
        self.add("leaf", deps=["mid"])
        self.add("other")
        self.add("joint", deps=["other", "mid"])
        r = self.run_cli("fail", "root")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.statuses(), {
            "root": "failed", "mid": "cancelled", "leaf": "cancelled",
            "other": "ready", "joint": "cancelled"})
        self.assertEqual(self.run_cli("fail", "root").returncode, 1)
        self.assertEqual(self.run_cli("fail", "nope").returncode, 1)


class RunNextTests(Base):
    def test_highest_priority_ready_runs(self):
        self.add("a", priority=3)
        self.add("b", priority=9)
        self.add("c", priority=10, deps=["a"])
        r = self.run_cli("run-next")
        self.assertIn("b", r.stdout)
        self.assertEqual(self.statuses(), {"a": "ready", "b": "done", "c": "pending"})
        self.run_cli("run-next")
        self.assertEqual(self.statuses(), {"a": "done", "b": "done", "c": "ready"})
        self.run_cli("run-next")
        self.assertEqual(set(self.statuses().values()), {"done"})
        r = self.run_cli("run-next")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no ready job", r.stdout)


class PersistenceTests(Base):
    def test_state_persists_in_json(self):
        self.add("a", priority=7, name="Alpha job")
        self.add("b", deps=["a"])
        data = self.raw()
        self.assertEqual(data["jobs"][0], {"id": "a", "name": "Alpha job", "priority": 7,
                                           "depends_on": [], "status": "pending"})
        self.assertEqual(data["jobs"][1]["depends_on"], ["a"])
        self.run_cli("fail", "a")
        self.assertEqual({j["id"]: j["status"] for j in self.raw()["jobs"]},
                         {"a": "failed", "b": "cancelled"})


class CliTests(Base):
    def test_all_commands_end_to_end(self):
        self.assertEqual(self.add("build", 8).returncode, 0)
        self.assertEqual(self.add("test", 6, ["build"]).returncode, 0)
        self.assertEqual(self.add("deploy", 4, ["test"]).returncode, 0)
        self.assertEqual(self.run_cli("run-next").returncode, 0)
        st = self.run_cli("status")
        self.assertEqual(st.returncode, 0)
        self.assertIn("test", st.stdout)
        self.assertEqual(self.run_cli("fail", "test").returncode, 0)
        rep = self.run_cli("report")
        self.assertEqual(rep.returncode, 0)
        self.assertIn("cancelled: 1", rep.stdout)
        self.assertIn("failed: 1", rep.stdout)
        self.assertIn("done: 1", rep.stdout)


if __name__ == "__main__":
    unittest.main()
