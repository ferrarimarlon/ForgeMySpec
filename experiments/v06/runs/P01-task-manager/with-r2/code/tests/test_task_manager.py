import ast
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "task_manager.py")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self._tmp.name, "t.db")

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "TASK_DB"}
        return subprocess.run([sys.executable, SCRIPT, "--db", self.db, *args],
                              capture_output=True, text=True, env=env)

    def rows(self):
        c = sqlite3.connect(self.db)
        try:
            return c.execute("SELECT id,title,description,priority,status,due_date "
                             "FROM tasks ORDER BY id").fetchall()
        finally:
            c.close()


class CrudTests(Base):
    def test_add_update_delete_roundtrip(self):
        r = self.cli("add", "Write", "-d", "docs", "-p", "high", "--due", "2030-01-02")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows(), [(1, "Write", "docs", "high", "todo", "2030-01-02")])
        self.assertIn("Write", self.cli("list").stdout)
        r = self.cli("update", "1", "--title", "Edit", "-s", "in-progress")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows(), [(1, "Edit", "docs", "high", "in-progress", "2030-01-02")])
        self.assertEqual(self.cli("delete", "1").returncode, 0)
        self.assertEqual(self.rows(), [])
        for cmd in (("update", "9", "--title", "x"), ("delete", "9")):
            self.assertEqual(self.cli(*cmd).returncode, 1)


class ValidationTests(Base):
    def test_invalid_values_rejected(self):
        for args in (("add", "t", "-p", "urgent"), ("add", "t", "-s", "blocked"),
                     ("add", "  "), ("add", "t", "--due", "2030-13-40"),
                     ("add", "t", "--due", "tomorrow")):
            r = self.cli(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("error", r.stderr)
        self.assertEqual(self.rows(), [])
        self.cli("add", "ok")
        self.assertEqual(self.cli("update", "1", "-p", "nope").returncode, 1)
        self.assertEqual(self.rows()[0][3], "medium")


class PersistenceTests(Base):
    def test_persists_across_invocations(self):
        self.cli("add", "a")
        self.cli("add", "b'; DROP TABLE tasks;--")
        out = self.cli("list").stdout
        self.assertIn("a", out)
        self.assertIn("DROP TABLE", out)
        self.assertEqual(len(self.rows()), 2)


class FilterTests(Base):
    def test_filter_by_status_and_priority(self):
        self.cli("add", "t1", "-p", "high")
        self.cli("add", "t2", "-p", "low", "-s", "done")
        self.cli("add", "t3", "-p", "high", "-s", "done")
        def titles(*a):
            out = self.cli("list", *a).stdout.splitlines()[2:]
            return [l.split()[1] for l in out]
        self.assertEqual(titles("--status", "done"), ["t2", "t3"])
        self.assertEqual(titles("--priority", "high"), ["t1", "t3"])
        self.assertEqual(titles("--status", "done", "--priority", "high"), ["t3"])
        self.assertEqual(self.cli("list", "--status", "bogus").returncode, 1)


class DoneTests(Base):
    def test_done_sets_status(self):
        self.cli("add", "x", "-p", "low", "--due", "2031-05-05")
        self.assertEqual(self.cli("done", "1").returncode, 0)
        self.assertEqual(self.rows(), [(1, "x", "", "low", "done", "2031-05-05")])
        self.assertEqual(self.cli("done", "5").returncode, 1)


class TableTests(Base):
    def test_table_has_header_and_aligned_columns(self):
        self.cli("add", "short")
        self.cli("add", "a much longer title", "-p", "high", "--due", "2030-01-01")
        lines = self.cli("list").stdout.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0].split(), ["ID", "TITLE", "PRIORITY", "STATUS", "DUE"])
        starts = [lines[0].index(h) for h in ("TITLE", "PRIORITY", "STATUS", "DUE")]
        self.assertEqual(lines[2].index("medium"), starts[1])
        self.assertEqual(lines[3].index("high"), starts[1])
        self.assertEqual(lines[3].index("2030-01-01"), starts[3])


class StructureTests(unittest.TestCase):
    def test_stdlib_only_single_file(self):
        with open(SCRIPT) as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        self.assertTrue(mods)
        self.assertLessEqual(mods, {"argparse", "datetime", "os", "sqlite3", "sys"})
        self.assertIn("sqlite3", mods)
        self.assertTrue(os.path.isfile(SCRIPT))


if __name__ == "__main__":
    unittest.main()
