import ast
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import task_manager

ROOT = Path(task_manager.__file__).resolve().parent


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "t.db")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = task_manager.main(["--db", self.db, *args])
            except SystemExit as e:
                code = e.code
        return code or 0, out.getvalue(), err.getvalue()

    def rows(self, *args):
        return task_manager.list_tasks(self.db, *args)

    def test_add_persists_across_invocations(self):
        code, out, _ = self.run_cli(
            "add", "Write docs", "-d", "the readme", "-p", "high", "--due", "2030-01-31")
        self.assertEqual(code, 0)
        self.assertIn("1", out)
        # a fresh process-like read through raw sqlite3
        import sqlite3
        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT id, title, description, priority, status, due_date FROM tasks").fetchone()
        conn.close()
        self.assertEqual(row, (1, "Write docs", "the readme", "high", "todo", "2030-01-31"))
        _, out, _ = self.run_cli("list")
        self.assertIn("Write docs", out)

    def test_invalid_priority_and_status_rejected(self):
        self.run_cli("add", "x")
        t = self.rows()[0]
        self.assertEqual((t["priority"], t["status"]), ("medium", "todo"))
        for args in (("add", "y", "-p", "urgent"),
                     ("update", "1", "--status", "finished"),
                     ("list", "--status", "bogus"),
                     ("list", "--priority", "bogus")):
            code, _, err = self.run_cli(*args)
            self.assertNotEqual(code, 0, args)
            self.assertTrue(err.strip(), args)
        self.assertEqual(len(self.rows()), 1)
        for p in ("low", "medium", "high"):
            self.assertEqual(self.run_cli("add", p, "-p", p)[0], 0)
        for s in ("todo", "in-progress", "done"):
            self.assertEqual(self.run_cli("update", "1", "--status", s)[0], 0)

    def test_update_and_delete(self):
        self.run_cli("add", "Old", "-d", "desc", "-p", "low", "--due", "2030-02-02")
        code, _, _ = self.run_cli("update", "1", "--title", "New", "--priority", "high")
        self.assertEqual(code, 0)
        t = self.rows()[0]
        self.assertEqual(
            (t["title"], t["description"], t["priority"], t["status"], t["due_date"]),
            ("New", "desc", "high", "todo", "2030-02-02"))
        self.assertEqual(self.run_cli("update", "99", "--title", "z")[0], 1)
        self.assertEqual(self.run_cli("delete", "1")[0], 0)
        self.assertEqual(self.rows(), [])
        code, _, err = self.run_cli("delete", "1")
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip())

    def test_list_filters(self):
        self.run_cli("add", "a", "-p", "high")
        self.run_cli("add", "b", "-p", "low", "--status", "in-progress")
        self.run_cli("add", "c", "-p", "high", "--status", "done")
        titles = lambda *a: sorted(t["title"] for t in self.rows(*a))
        self.assertEqual(titles("done", None), ["c"])
        self.assertEqual(titles(None, "high"), ["a", "c"])
        self.assertEqual(titles("in-progress", "high"), [])
        self.assertEqual(titles("done", "high"), ["c"])
        _, out, _ = self.run_cli("list", "--priority", "high", "--status", "todo")
        self.assertIn("a", out)
        self.assertNotIn(" b ", out)

    def test_done_marks_task(self):
        self.run_cli("add", "t", "-d", "d", "-p", "low", "--due", "2030-03-03")
        self.assertEqual(self.run_cli("done", "1")[0], 0)
        t = self.rows()[0]
        self.assertEqual(
            (t["title"], t["description"], t["priority"], t["status"], t["due_date"]),
            ("t", "d", "low", "done", "2030-03-03"))
        self.assertNotEqual(self.run_cli("done", "42")[0], 0)

    def test_list_prints_table(self):
        self.run_cli("add", "Short", "-p", "low")
        self.run_cli("add", "A much longer title", "-p", "high", "--due", "2030-04-04")
        _, out, _ = self.run_cli("list")
        lines = out.splitlines()
        header = lines[0]
        for col in ("ID", "Title", "Priority", "Status", "Due"):
            self.assertIn(col, header)
        self.assertGreaterEqual(len(lines), 4)  # header, separator, 2 rows
        self.assertTrue(set(lines[1]) <= set("-+ "))
        body = lines[2:]
        self.assertEqual(len(body), 2)
        pos = header.index("Priority")
        self.assertTrue(body[0][pos:].startswith("low"))
        self.assertTrue(body[1][pos:].startswith("high"))

    def test_invalid_input_exits_nonzero(self):
        for args in (("add", ""), ("add", "   "),
                     ("add", "x", "--due", "2030-13-45"),
                     ("add", "x", "--due", "tomorrow"),
                     ("update", "5", "--title", "x"),
                     ("done", "5"), ("delete", "5")):
            code, _, err = self.run_cli(*args)
            self.assertNotEqual(code, 0, args)
            self.assertTrue(err.strip(), args)
        self.assertEqual(self.rows(), [])

    def test_only_stdlib_imports(self):
        tree = ast.parse((ROOT / "task_manager.py").read_text())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                self.assertEqual(n.level, 0)
                mods.add(n.module.split(".")[0])
        self.assertIn("sqlite3", mods)
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is not None:
            self.assertTrue(mods <= set(stdlib), mods - set(stdlib))
        self.assertFalse(mods & {"sqlalchemy", "peewee", "django", "tabulate", "rich"})


if __name__ == "__main__":
    unittest.main()
