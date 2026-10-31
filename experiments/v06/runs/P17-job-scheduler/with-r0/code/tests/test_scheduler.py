import contextlib
import io
import json
import os
import tempfile
import unittest

import scheduler


class Base(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scheduler.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def add(self, i, prio=5, deps=""):
        args = ["add", "--id", i, "--name", "n" + i, "--priority", str(prio)]
        if deps:
            args += ["--depends-on", deps]
        return self.cli(*args)

    def raw(self):
        with open("scheduler.json") as fh:
            return json.load(fh)

    def statuses(self):
        return {j["id"]: j["status"] for j in scheduler.load()}


class ValidationTests(Base):
    def test_add_rejections(self):
        self.assertEqual(self.add("a")[0], 0)
        before = open("scheduler.json").read()
        cases = [
            self.add("a"),                 # duplicate id
            self.add("b", deps="b"),       # self-dependency
            self.add("b", deps="zzz"),     # unknown dependency
            self.add("bad-id"),            # malformed id
            self.add("x" * 33),            # too long
            self.add("b", prio=0),         # priority low
            self.add("b", prio=11),        # priority high
        ]
        for code, _, err in cases:
            self.assertEqual(code, 1)
            self.assertTrue(err.startswith("error:"))
        self.assertIn("duplicate", cases[0][2])
        self.assertIn("self-dependency", cases[1][2])
        self.assertIn("unknown dependency", cases[2][2])
        self.assertEqual(open("scheduler.json").read(), before)

    def test_id_boundaries(self):
        self.assertEqual(self.add("x" * 32)[0], 0)
        self.assertEqual(self.add("A_9")[0], 0)
        self.assertEqual(self.add("")[0], 1)


class CycleTests(Base):
    def test_cycle_rejected(self):
        # a hand-edited file where a already depends on a not-yet-existing c
        with open("scheduler.json", "w") as fh:
            json.dump({"jobs": [{"id": "a", "name": "a", "priority": 5,
                                 "depends_on": ["c"], "status": "pending"}]}, fh)
        before = open("scheduler.json").read()
        code, _, err = self.add("c", deps="a")
        self.assertEqual(code, 1)
        self.assertIn("cycle", err)
        self.assertEqual(open("scheduler.json").read(), before)

    def test_would_create_cycle_transitive(self):
        jobs = [
            {"id": "a", "depends_on": ["c"]},
            {"id": "b", "depends_on": ["a"]},
        ]
        self.assertTrue(scheduler.would_create_cycle(jobs, "c", ["b"]))
        self.assertFalse(scheduler.would_create_cycle(jobs, "d", ["b"]))


class OrderTests(Base):
    def test_topological_with_priority(self):
        self.add("low", 1)
        self.add("hi", 9)
        self.add("mid", 5)
        self.add("child", 10, "low")      # high priority but needs low
        self.add("top_dep", 3, "hi,mid")
        order = [j["id"] for j in scheduler.execution_order(scheduler.load())]
        self.assertEqual(order, ["hi", "mid", "top_dep", "low", "child"])
        pos = {i: n for n, i in enumerate(order)}
        self.assertLess(pos["low"], pos["child"])
        code, out, _ = self.cli("report")
        self.assertEqual(code, 0)
        self.assertLess(out.index("hi "), out.index("child"))


class ReadyTests(Base):
    def test_ready_recomputed_on_load(self):
        self.add("a")
        self.add("b", 5, "a")
        self.assertEqual(self.statuses(), {"a": "ready", "b": "pending"})
        data = self.raw()
        data["jobs"][0]["status"] = "done"
        with open("scheduler.json", "w") as fh:
            json.dump(data, fh)
        self.assertEqual(self.statuses(), {"a": "done", "b": "ready"})
        # a stale persisted "ready" is not trusted
        data["jobs"][0]["status"] = "pending"
        data["jobs"][1]["status"] = "ready"
        with open("scheduler.json", "w") as fh:
            json.dump(data, fh)
        self.assertEqual(self.statuses(), {"a": "ready", "b": "pending"})


class FailTests(Base):
    def test_transitive_cancel(self):
        self.add("a")
        self.add("b", 5, "a")
        self.add("c", 5, "b")
        self.add("d", 5, "a")
        self.add("other", 5)
        code, out, _ = self.cli("fail", "a")
        self.assertEqual(code, 0)
        self.assertEqual(self.statuses(), {"a": "failed", "b": "cancelled",
                                           "c": "cancelled", "d": "cancelled",
                                           "other": "ready"})

    def test_fail_errors(self):
        self.add("a")
        self.assertEqual(self.cli("fail", "nope")[0], 1)
        self.cli("fail", "a")
        self.assertEqual(self.cli("fail", "a")[0], 1)


class RunNextTests(Base):
    def test_runs_highest_priority_ready(self):
        self.add("a", 3)
        self.add("b", 8)
        self.add("c", 10, "a")
        code, out, _ = self.cli("run-next")
        self.assertEqual(code, 0)
        self.assertIn("running b", out)
        self.assertEqual(self.statuses(), {"a": "ready", "b": "done", "c": "pending"})
        self.cli("run-next")
        self.assertEqual(self.statuses(), {"a": "done", "b": "done", "c": "ready"})
        self.cli("run-next")
        self.assertEqual(set(self.statuses().values()), {"done"})
        code, out, _ = self.cli("run-next")
        self.assertEqual(code, 0)
        self.assertIn("no ready job", out)


class PersistenceTests(Base):
    def test_ready_never_persisted(self):
        self.add("a")
        self.add("b", 5, "a")
        for cmd in (["status"], ["report"], ["run-next"]):
            self.cli(*cmd)
            for j in self.raw()["jobs"]:
                self.assertIn(j["status"], ("pending", "running", "done", "failed", "cancelled"))
        self.add("c")
        self.assertEqual({j["id"]: j["status"] for j in self.raw()["jobs"]}["c"], "pending")
        self.assertEqual(self.statuses()["c"], "ready")


class CliTests(Base):
    def test_all_commands(self):
        self.assertEqual(self.add("a")[0], 0)
        self.assertEqual(self.add("b", 5, "a")[0], 0)
        code, out, _ = self.cli("status")
        self.assertEqual(code, 0)
        self.assertIn("ready", out)
        self.assertEqual(self.cli("report")[0], 0)
        self.assertEqual(self.cli("run-next")[0], 0)
        self.assertEqual(self.cli("fail", "b")[0], 0)


if __name__ == "__main__":
    unittest.main()
