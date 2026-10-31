import contextlib
import io
import json
import os
import tempfile
import unittest

import scheduler


def J(jid, prio=5, deps=(), status="pending"):
    return {"id": jid, "name": jid, "priority": prio, "depends_on": list(deps), "status": status}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "state.json")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scheduler.main(["--file", self.path, *map(str, argv)])
        return code, out.getvalue(), err.getvalue()

    def add(self, jid, prio=5, deps=()):
        args = ["add", jid, "name_" + jid, prio]
        if deps:
            args += ["--depends-on", *deps]
        return self.run_cli(*args)

    def raw(self):
        with open(self.path) as fh:
            return json.load(fh)

    def statuses(self):
        return {j["id"]: j["status"] for j in self.raw()["jobs"]}

    def write(self, jobs):
        with open(self.path, "w") as fh:
            json.dump({"jobs": jobs}, fh)


class ValidationTests(Base):
    def test_id_and_priority_format(self):
        for bad in ["", "a-b", "a b", "x" * 33, "é"]:
            self.assertEqual(self.run_cli("add", bad, "n", 5)[0], 1, bad)
        self.assertEqual(self.add("x" * 32)[0], 0)
        self.assertEqual(self.add("A_1")[0], 0)
        for i, p in enumerate(["0", "11", "-1", "abc", "1.5"]):
            self.assertNotEqual(self.run_cli("add", "p%d" % i, "n", p)[0], 0, p)
        self.assertEqual(self.add("lo", 1)[0], 0)
        self.assertEqual(self.add("hi", 10)[0], 0)
        self.assertEqual(len(self.raw()["jobs"]), 4)

    def test_duplicate_id_rejected(self):
        self.add("a")
        before = self.raw()
        code, _, err = self.add("a", 9)
        self.assertEqual(code, 1)
        self.assertIn("duplicate", err)
        self.assertEqual(self.raw(), before)

    def test_self_dependency_rejected(self):
        code, _, err = self.add("a", 5, ["a"])
        self.assertEqual(code, 1)
        self.assertIn("self-dependency", err)
        self.assertFalse(os.path.exists(self.path))

    def test_unknown_dependency_rejected(self):
        self.add("a")
        before = self.raw()
        code, _, err = self.add("b", 5, ["ghost"])
        self.assertEqual(code, 1)
        self.assertIn("unknown dependency", err)
        self.assertEqual(self.raw(), before)


class CycleTests(Base):
    def test_cycle_rejected(self):
        self.assertIsNotNone(scheduler.find_cycle({"a": J("a", deps=["b"]), "b": J("b", deps=["a"])}))
        self.assertIsNone(scheduler.find_cycle({"a": J("a"), "b": J("b", deps=["a"])}))
        # add_job runs the cycle check on the resulting graph: an existing job
        # that already points at the new id (hand-edited state) closes a cycle.
        jobs = {"a": J("a", deps=["n"])}
        with self.assertRaises(scheduler.SchedulerError) as ctx:
            scheduler.add_job(jobs, "n", "n", 5, ["a"])
        self.assertIn("cycle", str(ctx.exception))
        self.assertNotIn("n", jobs)
        # a state file that already holds a cycle is rejected on load
        self.write([J("a", deps=["b"]), J("b", deps=["a"])])
        code, _, err = self.run_cli("add", "c", "c", 5)
        self.assertEqual(code, 1)
        self.assertIn("cycle", err)
        self.assertEqual(self.raw()["jobs"][0]["id"], "a")
        self.assertEqual(len(self.raw()["jobs"]), 2)


class OrderTests(Base):
    def test_topological_with_priority_tiebreak(self):
        self.add("low", 1)
        self.add("high", 9)
        self.add("mid", 5)
        self.add("child_hi", 10, ["low"])
        self.add("child_lo", 2, ["high", "mid"])
        order = scheduler.execution_order(scheduler.load(self.path))
        self.assertEqual(order, ["high", "mid", "child_lo", "low", "child_hi"])


class ReadyTests(Base):
    def test_ready_recomputed_on_load(self):
        self.write([J("a", status="done"), J("b", deps=["a"]), J("c", deps=["b"]),
                    J("d", status="ready", deps=["c"])])
        jobs = scheduler.load(self.path)
        self.assertEqual({k: v["status"] for k, v in jobs.items()},
                         {"a": "done", "b": "ready", "c": "pending", "d": "pending"})
        self.assertIn("b\tready", self.run_cli("status")[1])

    def test_ready_never_persisted(self):
        self.add("a")
        self.add("b", 5, ["a"])
        self.assertNotIn("ready", self.statuses().values())
        self.run_cli("run-next")
        self.run_cli("status")
        self.assertNotIn("ready", self.statuses().values())
        with open(self.path) as fh:
            self.assertNotIn('"ready"', fh.read())


class FailureTests(Base):
    def test_failure_cancels_transitive_dependents(self):
        self.add("a")
        self.add("b", 5, ["a"])
        self.add("c", 5, ["b"])
        self.add("d", 5, ["a", "c"])
        self.add("x")
        self.assertEqual(self.run_cli("fail", "a")[0], 0)
        self.assertEqual(self.statuses(), {"a": "failed", "b": "cancelled", "c": "cancelled",
                                           "d": "cancelled", "x": "pending"})
        self.assertEqual(self.run_cli("fail", "a")[0], 1)
        self.assertEqual(self.run_cli("fail", "nope")[0], 1)
        self.add("e", 5, ["a"])
        self.assertEqual(self.statuses()["e"], "cancelled")


class RunNextTests(Base):
    def test_run_next_highest_priority(self):
        self.assertIn("no ready", self.run_cli("run-next")[1])
        self.add("low", 2)
        self.add("high", 8)
        self.add("child", 10, ["high"])
        self.run_cli("run-next")
        self.assertEqual(self.statuses(), {"low": "pending", "high": "done", "child": "pending"})
        self.run_cli("run-next")  # child (10) is now ready and beats low (2)
        self.assertEqual(self.statuses()["child"], "done")
        self.assertEqual(self.statuses()["low"], "pending")
        self.run_cli("run-next")
        self.assertEqual(set(self.statuses().values()), {"done"})
        self.assertIn("no ready", self.run_cli("run-next")[1])

    def test_running_is_set_before_done(self):
        self.add("a")
        seen = []
        orig = scheduler.save

        def spy(path, jobs):
            seen.append(jobs["a"]["status"])
            orig(path, jobs)
        scheduler.save = spy
        try:
            self.run_cli("run-next")
        finally:
            scheduler.save = orig
        self.assertEqual(seen, ["running", "done"])


class CliTests(Base):
    def test_all_commands(self):
        self.assertEqual(self.add("a", 3)[0], 0)
        self.assertEqual(self.add("b", 7, ["a"])[0], 0)
        self.assertEqual(self.add("c", 1)[0], 0)
        code, out, _ = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("a\tready", out)
        self.assertIn("b\tpending", out)
        self.assertEqual(self.run_cli("run-next")[0], 0)
        code, out, _ = self.run_cli("report")
        self.assertEqual(code, 0)
        self.assertIn("done: 1", out)
        self.assertIn("execution order: b -> c", out)
        self.assertEqual(self.run_cli("fail", "b")[0], 0)
        self.assertEqual(self.statuses(), {"a": "done", "b": "failed", "c": "pending"})
        self.assertEqual(self.run_cli("bogus")[0], 2)
        self.assertEqual(self.run_cli()[0], 2)


if __name__ == "__main__":
    unittest.main()
