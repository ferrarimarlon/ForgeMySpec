import ast
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "note_taker.py"


class NoteTakerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "notes"  # missing on purpose
        self.env = dict(os.environ, NOTE_TAKER_DIR=str(self.dir))

    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True,
                              env=env or self.env, stdin=subprocess.DEVNULL)

    def test_new_writes_frontmatter_note(self):
        r = self.run_cli("new", "Hello World", "-t", "a", "-t", "b", "-b", "body text")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "hello-world")
        text = (self.dir / "hello-world.md").read_text()
        lines = text.split("\n")
        self.assertEqual(lines[0], "---")
        self.assertIn('title: "Hello World"', lines)
        self.assertIn('tags: ["a", "b"]', lines)
        self.assertTrue(any(l.startswith("created: ") for l in lines))
        self.assertEqual(lines[4], "---")
        self.assertEqual(lines[5], "body text")
        # duplicate title gets a distinct id
        r2 = self.run_cli("new", "Hello World")
        self.assertEqual(r2.stdout.strip(), "hello-world-2")

    def test_list_search_filters(self):
        self.run_cli("new", "Groceries", "-t", "home", "-b", "Buy MILK")
        self.run_cli("new", "Work plan", "-t", "work", "-b", "ship it")
        self.run_cli("new", "Milkshake", "-t", "home,x", "-b", "yum")
        out = self.run_cli("list").stdout
        self.assertEqual(len(out.strip().splitlines()), 3)
        out = self.run_cli("list", "--tag", "work").stdout
        self.assertIn("work-plan", out)
        self.assertNotIn("groceries", out)
        out = self.run_cli("list", "--search", "milk").stdout
        self.assertIn("groceries", out)   # body, case-insensitive
        self.assertIn("milkshake", out)   # title
        self.assertNotIn("work-plan", out)
        out = self.run_cli("list", "--tag", "home", "--search", "ship").stdout
        self.assertEqual(out.strip(), "")
        # empty / missing directory lists nothing
        env = dict(self.env, NOTE_TAKER_DIR=str(Path(self.tmp.name) / "none"))
        self.assertEqual(self.run_cli("list", env=env).returncode, 0)

    def test_show_prints_or_fails(self):
        self.run_cli("new", "Alpha", "-b", "line one")
        r = self.run_cli("show", "alpha")
        self.assertEqual(r.returncode, 0)
        self.assertIn('title: "Alpha"', r.stdout)
        self.assertIn("line one", r.stdout)
        r = self.run_cli("show", "missing")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no such note", r.stderr)
        self.assertEqual(self.run_cli("show", "../etc/passwd").returncode, 1)

    def _editor(self, body):
        p = Path(self.tmp.name) / "ed.sh"
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        return dict(self.env, EDITOR=str(p))

    def test_edit_and_delete(self):
        self.run_cli("new", "Beta", "-b", "old")
        env = self._editor('echo edited >> "$1"')
        r = self.run_cli("edit", "beta", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("edited", (self.dir / "beta.md").read_text())
        env = self._editor(': > "$1"')
        r = self.run_cli("edit", "beta", env=env)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.run_cli("edit", "nope", env=env).returncode, 1)
        r = self.run_cli("delete", "beta")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.dir / "beta.md").exists())
        self.assertEqual(self.run_cli("delete", "beta").returncode, 1)

    def test_single_file_stdlib(self):
        tree = ast.parse(SCRIPT.read_text())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                mods.add(node.module.split(".")[0])
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:
            stdlib = {"argparse", "datetime", "os", "re", "shlex", "subprocess", "sys", "pathlib"}
        self.assertTrue(mods)
        self.assertEqual(mods - set(stdlib), set())


if __name__ == "__main__":
    unittest.main()
