import ast
import contextlib
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import note_taker  # noqa: E402


class NoteTakerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "notes")
        self._old = {k: os.environ.get(k) for k in ("NOTE_TAKER_DIR", "EDITOR")}
        os.environ["NOTE_TAKER_DIR"] = self.dir

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = note_taker.main(list(argv))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def test_new_writes_md_with_frontmatter(self):
        rc, out, _ = self.run_cli("new", "Hello World", "-t", "a,b", "-t", "c", "-b", "body text")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "hello-world")
        with open(os.path.join(self.dir, "hello-world.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\n"))
        self.assertIn('title: "Hello World"', text)
        self.assertIn('tags: ["a", "b", "c"]', text)
        self.assertIn("created: ", text)
        self.assertTrue(text.rstrip().endswith("body text"))
        rc, out, _ = self.run_cli("new", "Hello World", "-b", "x")
        self.assertEqual(out.strip(), "hello-world-2")

    def test_default_dir_is_home_note_taker(self):
        del os.environ["NOTE_TAKER_DIR"]
        self.assertEqual(note_taker.notes_dir(), os.path.join(os.path.expanduser("~"), ".note-taker"))

    def test_list_filters_by_tag_and_keyword(self):
        self.run_cli("new", "Groceries", "-t", "home", "-b", "buy Milk")
        self.run_cli("new", "Work plan", "-t", "work", "-b", "ship it")
        rc, out, _ = self.run_cli("list")
        self.assertEqual(len(out.strip().splitlines()), 2)
        _, out, _ = self.run_cli("list", "--tag", "home")
        self.assertIn("groceries", out)
        self.assertNotIn("work-plan", out)
        _, out, _ = self.run_cli("list", "--search", "milk")
        self.assertIn("groceries", out)
        self.assertNotIn("work-plan", out)
        _, out, _ = self.run_cli("list", "--search", "WORK")
        self.assertIn("work-plan", out)
        _, out, _ = self.run_cli("list", "--tag", "nope")
        self.assertEqual(out.strip(), "")

    def test_list_when_dir_missing(self):
        rc, out, _ = self.run_cli("list")
        self.assertEqual((rc, out), (0, ""))

    def test_show_and_edit(self):
        self.run_cli("new", "Doc", "-t", "x", "-b", "first")
        rc, out, _ = self.run_cli("show", "doc")
        self.assertEqual(rc, 0)
        self.assertIn("# Doc", out)
        self.assertIn("first", out)
        os.environ["EDITOR"] = "sh -c 'echo edited >> \"$0\"'"
        path = os.path.join(self.dir, "doc.md")
        with open(path) as f:
            before = f.read()
        rc, _, _ = self.run_cli("edit", "doc")
        self.assertEqual(rc, 0)
        with open(path) as f:
            after = f.read()
        self.assertIn("edited", after)
        self.assertIn('title: "Doc"', after)
        self.assertNotEqual(before, after)
        os.environ["EDITOR"] = "false"
        rc, _, err = self.run_cli("edit", "doc")
        self.assertEqual(rc, 1)
        self.assertIn("editor", err)

    def test_delete_and_bad_ids(self):
        self.run_cli("new", "Gone", "-b", "x")
        rc, _, _ = self.run_cli("delete", "gone")
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "gone.md")))
        for cmd in ("show", "edit", "delete"):
            rc, _, err = self.run_cli(cmd, "gone")
            self.assertEqual(rc, 1)
            self.assertIn("no such note", err)
        outside = os.path.join(self.tmp.name, "victim.md")
        with open(outside, "w") as f:
            f.write("x")
        for bad in ("../victim", "/etc/passwd", "sub" + os.sep + "x", ".."):
            rc, _, err = self.run_cli("delete", bad)
            self.assertEqual(rc, 1, bad)
            self.assertIn("invalid note id", err)
        self.assertTrue(os.path.exists(outside))

    def test_stdlib_only(self):
        with open(os.path.join(ROOT, "note_taker.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        allowed = getattr(sys, "stdlib_module_names", None) or {
            "argparse", "datetime", "json", "os", "re", "shlex", "subprocess", "sys", "__future__"}
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertTrue(mods)
        self.assertFalse(mods - set(allowed), mods - set(allowed))


if __name__ == "__main__":
    unittest.main()
