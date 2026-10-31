import ast
import contextlib
import io
import json
import os
import tempfile
import unittest

import state_machine as sm

MACHINE = {
    "states": ["idle", "running", "done"],
    "initial": "idle",
    "final": ["done"],
    "transitions": [
        {"from": "idle", "event": "start", "to": "running"},
        {"from": "running", "event": "finish", "to": "done",
         "guard": {"key": "ready", "op": "==", "value": True}},
    ],
}


def write(data, raw=False):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    f.write(data if raw else json.dumps(data))
    f.close()
    return f.name


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = sm.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class LoadTests(unittest.TestCase):
    def test_load_and_malformed(self):
        self.assertEqual(sm.load_machine(write(MACHINE)), MACHINE)
        self.assertEqual(cli("validate", write("{nope", raw=True))[0], 2)
        self.assertEqual(cli("validate", "/no/such/file.json")[0], 2)
        self.assertEqual(cli("validate", write("[1]", raw=True))[0], 2)


class ValidateTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(sm.validate(MACHINE), [])

    def test_unknown_states(self):
        m = json.loads(json.dumps(MACHINE))
        m["transitions"].append({"from": "idle", "event": "x", "to": "ghost"})
        m["final"].append("phantom")
        m["initial"] = "idle"
        errs = "\n".join(sm.validate(m))
        self.assertIn("ghost", errs)
        self.assertIn("phantom", errs)
        m["initial"] = "nowhere"
        self.assertIn("nowhere", "\n".join(sm.validate(m)))

    def test_unreachable_states(self):
        m = json.loads(json.dumps(MACHINE))
        m["states"].append("orphan")
        errs = sm.validate(m)
        self.assertIn("unreachable state: orphan", errs)
        self.assertEqual(len(errs), 1)

    def test_missing_initial(self):
        for bad in ("", None):
            m = dict(MACHINE, initial=bad)
            self.assertIn("missing initial state", sm.validate(m))
        m = dict(MACHINE)
        del m["initial"]
        self.assertIn("missing initial state", sm.validate(m))
        self.assertEqual(cli("validate", write(m))[0], 1)


class RunTests(unittest.TestCase):
    def test_guard_on_context(self):
        r = sm.Runner(MACHINE, {"ready": False})
        r.run(["start", "finish"])
        self.assertEqual(r.state, "running")
        r = sm.Runner(MACHINE, {"ready": True})
        r.run(["start", "finish"])
        self.assertEqual(r.state, "done")
        m = json.loads(json.dumps(MACHINE))
        m["transitions"].insert(1, {"from": "running", "event": "finish", "to": "idle",
                                    "guard": {"key": "n", "op": ">", "value": 3}})
        r = sm.Runner(m, {"n": 5})
        r.run(["start", "finish"])
        self.assertEqual(r.state, "idle")
        r = sm.Runner(m, {})  # missing key -> guard fails
        r.run(["start", "finish"])
        self.assertEqual(r.state, "running")

    def test_run_sequence_and_rejection(self):
        r = sm.Runner(MACHINE, {"ready": True})
        self.assertEqual(r.run(["bogus", "start", "finish", "start"]),
                         [False, True, True, False])
        self.assertEqual(r.state, "done")
        self.assertEqual(r.history[0]["to"], "idle")  # unchanged on rejection
        self.assertIn("final", r.history[3]["outcome"])

    def test_history_format(self):
        r = sm.Runner(MACHINE, {"ready": True})
        r.run(["start", "nope"])
        lines = sm.format_history(r.history).splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "1. idle --start--> running [ok]")
        self.assertTrue(lines[1].startswith("2. running --nope--> running [rejected"))


class CliTests(unittest.TestCase):
    def test_exit_codes_and_stdlib_imports(self):
        path = write(MACHINE)
        code, out, _ = cli("validate", path)
        self.assertEqual((code, out.strip()), (0, "valid"))
        code, out, _ = cli("run", path, "start", "finish", "--context", '{"ready": true}')
        self.assertEqual(code, 0)
        self.assertIn("1. idle --start--> running [ok]", out)
        self.assertIn("final state: done", out)
        self.assertEqual(cli("run", path, "start", "finish")[0], 1)  # guard blocks
        self.assertEqual(cli("run", path, "start", "--context", "{x")[0], 2)
        self.assertEqual(cli()[0], 2)
        bad = dict(MACHINE, states=MACHINE["states"] + ["orphan"])
        self.assertEqual(cli("run", write(bad), "start")[0], 1)
        # stdlib only
        tree = ast.parse(open(sm.__file__, encoding="utf-8").read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        allowed = {"argparse", "json", "operator", "sys"}
        self.assertTrue(mods <= allowed, mods)


if __name__ == "__main__":
    unittest.main()
