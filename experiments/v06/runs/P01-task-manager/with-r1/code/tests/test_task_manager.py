import ast
import contextlib
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import task_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "task_manager.py")


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "t.db")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = task_manager.main(["--db", self.db] + list(args))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def rows(self):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT id, title, description, priority, status, due_date FROM tasks ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

    def test_crud_roundtrip(self):
        code, out, _ = self.run_cli("add", "Write", "-d", "docs", "-p", "high", "--due", "2030-01-02")
        self.assertEqual(code, 0)
        self.assertEqual(self.rows(), [(1, "Write", "docs", "high", "todo", "2030-01-02")])
        _, out, _ = self.run_cli("list")
        self.assertIn("Write", out)
        self.assertEqual(self.run_cli("update", "1", "--title", "Edit", "-s", "in-progress")[0], 0)
        self.assertEqual(self.rows(), [(1, "Edit", "docs", "high", "in-progress", "2030-01-02")])
        self.assertEqual(self.run_cli("delete", "1")[0], 0)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.run_cli("delete", "1")[0], 1)
        self.assertEqual(self.run_cli("update", "9", "--title", "x")[0], 1)

    def test_invalid_values_rejected(self):
        for args in (["add", "a", "-p", "urgent"], ["add", "a", "-s", "blocked"],
                     ["add", "a", "--due", "tomorrow"]):
            code, _, err = self.run_cli(*args)
            self.assertEqual(code, 1)
            self.assertIn("error", err)
        self.assertEqual(self.rows(), [])
        self.run_cli("add", "ok")
        self.assertEqual(self.run_cli("update", "1", "-p", "none")[0], 1)
        self.assertEqual(self.rows()[0][3], "medium")
        self.assertEqual(self.run_cli("list", "--status", "bogus")[0], 1)

    def test_persists_between_invocations(self):
        cmd = [sys.executable, SCRIPT, "--db", self.db]
        subprocess.run(cmd + ["add", "Persist"], check=True, capture_output=True)
        res = subprocess.run(cmd + ["list"], check=True, capture_output=True, text=True)
        self.assertIn("Persist", res.stdout)
        self.assertEqual(len(self.rows()), 1)

    def test_filters(self):
        self.run_cli("add", "A", "-p", "high", "-s", "todo")
        self.run_cli("add", "B", "-p", "low", "-s", "done")
        self.run_cli("add", "C", "-p", "high", "-s", "done")
        titles = lambda *a: [r[1] for r in task_manager.list_tasks(
            sqlite3.connect(self.db), *a)]
        self.assertEqual(titles("done", None), ["B", "C"])
        self.assertEqual(titles(None, "high"), ["A", "C"])
        self.assertEqual(titles("done", "high"), ["C"])
        _, out, _ = self.run_cli("list", "--status", "done", "--priority", "high")
        self.assertIn("C", out)
        self.assertNotIn("| A ", out)
        self.assertNotIn("| B ", out)

    def test_done(self):
        self.run_cli("add", "A")
        self.run_cli("add", "B")
        self.assertEqual(self.run_cli("done", "1")[0], 0)
        self.assertEqual([r[4] for r in self.rows()], ["done", "todo"])
        self.assertEqual(self.run_cli("done", "5")[0], 1)

    def test_table_output(self):
        self.run_cli("add", "Short")
        self.run_cli("add", "A much longer title", "-p", "low")
        _, out, _ = self.run_cli("list")
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 6)  # border, header, border, 2 rows, border
        for name in ("ID", "TITLE", "DESCRIPTION", "PRIORITY", "STATUS", "DUE_DATE"):
            self.assertIn(name, lines[1])
        self.assertEqual(len({len(l) for l in lines}), 1)
        self.assertIn("Short", lines[3])

    def test_stdlib_only_imports(self):
        with open(SCRIPT) as f:
            tree = ast.parse(f.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        stdlib = getattr(sys, 'stdlib_module_names', None) or {
            'argparse', 'datetime', 'sqlite3', 'sys', 'os', 'io', 'json', 'textwrap'}
        self.assertLessEqual(mods, set(stdlib))


if __name__ == "__main__":
    unittest.main()
