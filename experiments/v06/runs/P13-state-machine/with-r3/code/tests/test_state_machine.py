import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

import state_machine as sm

BASE = {
    "states": ["idle", "running", "done"],
    "initial": "idle",
    "finals": ["done"],
    "transitions": [
        {"from": "idle", "event": "start", "to": "running"},
        {"from": "running", "event": "finish", "to": "done",
         "guard": {"key": "ok", "op": "==", "value": True}},
    ],
}


def cli(defn, *args, raw=None):
    """Run main() on a temp definition file; return (code, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.json")
        with open(path, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(defn))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sm.main([path, *args])
    return code, out.getvalue(), err.getvalue()


def variant(**changes):
    d = json.loads(json.dumps(BASE))
    d.update(changes)
    return d


class LoadTests(unittest.TestCase):
    def test_load_and_bad_input(self):
        code, out, _ = cli(BASE)
        self.assertEqual(code, 0)
        self.assertIn("state: idle", out)
        self.assertEqual(cli(None, raw="{not json")[0], 2)
        self.assertEqual(cli(None, raw="[1, 2]")[0], 2)
        self.assertEqual(cli(variant(states="abc"))[0], 2)
        bad_guard = variant(transitions=[{"from": "idle", "event": "e", "to": "running",
                                          "guard": {"key": "x", "op": "~", "value": 1}}])
        self.assertEqual(cli(bad_guard)[0], 2)
        self.assertEqual(cli(BASE, "--context", "[1]")[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sm.main(["/nonexistent/m.json"]), 2)


class ValidateTests(unittest.TestCase):
    def test_unknown_states(self):
        d = variant(finals=["ghost"], transitions=[
            {"from": "idle", "event": "x", "to": "nowhere"},
            {"from": "phantom", "event": "y", "to": "running"}])
        code, _, err = cli(d)
        self.assertEqual(code, 2)
        for name in ("ghost", "nowhere", "phantom"):
            self.assertIn(name, err)
        self.assertIn("unknown state", err)
        code, _, err = cli(variant(initial="zzz"))
        self.assertEqual(code, 2)
        self.assertIn("unknown state 'zzz'", err)

    def test_unreachable_states(self):
        d = variant(states=["idle", "running", "done", "island"])
        code, _, err = cli(d)
        self.assertEqual(code, 2)
        self.assertIn("unreachable state 'island'", err)
        self.assertEqual(sm.validate(BASE), [])

    def test_missing_initial(self):
        d = variant()
        del d["initial"]
        code, _, err = cli(d)
        self.assertEqual(code, 2)
        self.assertIn("missing initial state", err)


class RunTests(unittest.TestCase):
    def test_guards(self):
        d = variant(states=["a", "b", "c"], initial="a", finals=["c"], transitions=[
            {"from": "a", "event": "go", "to": "b",
             "guard": [{"key": "n", "op": ">=", "value": 5},
                       {"key": "role", "op": "in", "value": ["admin", "ops"]}]},
            {"from": "a", "event": "go", "to": "c"},
        ])
        run = lambda ctx: sm.run_events(d, ["go"], ctx)
        self.assertEqual(run({"n": 5, "role": "admin"})[1], "b")
        self.assertEqual(run({"n": 4, "role": "admin"})[1], "c")   # guard false -> next
        self.assertEqual(run({"n": 9, "role": "guest"})[1], "c")
        self.assertEqual(run({"role": "admin"})[1], "c")            # missing key is false
        self.assertEqual(run({"n": "text", "role": "ops"})[1], "c")  # type error is false
        # first enabled transition wins
        self.assertEqual(sm.run_events(d, ["go"], {"n": 7, "role": "ops"})[0],
                         [("a", "go", "b")])

    def test_run_and_reject(self):
        code, out, _ = cli(BASE, "start", "finish", "--context", '{"ok": true}')
        self.assertEqual(code, 0)
        self.assertIn("state: done (final)", out)
        # guard blocks: rejected, run stops, exit 1, earlier history kept
        code, out, err = cli(BASE, "start", "finish", "--context", '{"ok": false}')
        self.assertEqual(code, 1)
        self.assertIn("idle --start--> running", out)
        self.assertIn("rejected", err)
        code, _, _ = cli(BASE, "bogus")
        self.assertEqual(code, 1)
        # events after a rejection are not applied
        hist, state, rej = sm.run_events(BASE, ["bogus", "start"], {})
        self.assertEqual((hist, state, rej), ([], "idle", "bogus"))


class HistoryTests(unittest.TestCase):
    def test_history_printed(self):
        code, out, _ = cli(BASE, "start", "finish", "--context", '{"ok": true}')
        self.assertEqual(code, 0)
        self.assertIn("1. idle --start--> running", out)
        self.assertIn("2. running --finish--> done", out)
        self.assertLess(out.index("1. idle"), out.index("2. running"))
        self.assertIn("(no transitions)", cli(BASE)[1])
        self.assertEqual(sm.run_events(BASE, ["start"], {})[0], [("idle", "start", "running")])


class PackagingTests(unittest.TestCase):
    def test_stdlib_only(self):
        path = os.path.join(os.path.dirname(os.path.abspath(sm.__file__)), "state_machine.py")
        with open(path) as fh:
            src = fh.read()
        mods = set(re.findall(r"^\s*import (\w+)", src, re.M))
        mods |= set(re.findall(r"^\s*from (\w+) import", src, re.M))
        self.assertTrue(mods)
        for m in mods:
            self.assertIn(m, {"argparse", "json", "operator", "sys"}, m)
        self.assertNotIn("eval(", src.replace("no eval", ""))


if __name__ == "__main__":
    unittest.main()
