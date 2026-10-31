import ast
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

import note_taker

ROOT = Path(__file__).resolve().parent.parent


class NoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "notes"  # does not exist yet
        self._old = {k: os.environ.get(k) for k in ("NOTE_TAKER_DIR", "EDITOR", "VISUAL")}
        os.environ["NOTE_TAKER_DIR"] = str(self.dir)
        os.environ.pop("VISUAL", None)

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = note_taker.main(list(args))
            except SystemExit as e:
                code = e.code
        return code or 0, out.getvalue(), err.getvalue()

    def new(self, title, body="", tags=""):
        args = ["new", title, "--body", body]
        if tags:
            args += ["--tags", tags]
        code, out, _ = self.run_cli(*args)
        self.assertEqual(code, 0)
        return out.strip()

    def test_new_writes_md_with_frontmatter(self):
        nid = self.new("Hello World", "some body", "a,b")
        path = self.dir / f"{nid}.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("title: Hello World", text)
        self.assertIn("tags: [a, b]", text)
        self.assertIn("created:", text)
        self.assertTrue(text.rstrip().endswith("some body"))
        nid2 = self.new("Hello World", "other")
        self.assertNotEqual(nid, nid2)
        self.assertIn("some body", path.read_text(encoding="utf-8"))
        self.assertEqual(len(list(self.dir.glob("*.md"))), 2)

    def test_show_roundtrip(self):
        nid = self.new("Tricky: title, #1", "line1\n\nline2", "x, Y")
        code, out, _ = self.run_cli("show", nid)
        self.assertEqual(code, 0)
        self.assertIn("Tricky: title, #1", out)
        self.assertIn("x", out)
        self.assertIn("line1\n\nline2", out)
        meta, body = note_taker.parse_note((self.dir / f"{nid}.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["title"], "Tricky: title, #1")
        self.assertEqual(meta["tags"], ["x", "y"])
        self.assertEqual(body.strip(), "line1\n\nline2")

    def test_list_filters_by_tag_and_keyword(self):
        a = self.new("Alpha", "mentions banana", "fruit")
        b = self.new("Beta", "plain", "work")
        c = self.new("Gamma Banana", "x", "")
        _, out, _ = self.run_cli("list")
        for nid in (a, b, c):
            self.assertIn(nid, out)
        _, out, _ = self.run_cli("list", "--tag", "FRUIT")
        self.assertIn(a, out)
        self.assertNotIn(b, out)
        self.assertNotIn(c, out)
        _, out, _ = self.run_cli("list", "--search", "banana")
        self.assertIn(a, out)
        self.assertIn(c, out)
        self.assertNotIn(b, out)
        _, out, _ = self.run_cli("list", "--tag", "work", "--search", "banana")
        self.assertEqual(out.strip(), "")

    def test_edit_and_delete(self):
        nid = self.new("Edit me", "old")
        path = self.dir / f"{nid}.md"
        good = Path(self.tmp.name) / "good.py"
        good.write_text(
            "import sys\np=sys.argv[1]\nt=open(p).read().replace('old','new')\nopen(p,'w').write(t)\n"
        )
        os.environ["EDITOR"] = f"python3 {good}"
        code, _, _ = self.run_cli("edit", nid)
        self.assertEqual(code, 0)
        self.assertIn("new", path.read_text(encoding="utf-8"))
        bad = Path(self.tmp.name) / "bad.py"
        bad.write_text("import sys\nopen(sys.argv[1],'w').write('no frontmatter')\n")
        before = path.read_text(encoding="utf-8")
        os.environ["EDITOR"] = f"python3 {bad}"
        code, _, err = self.run_cli("edit", nid)
        self.assertEqual(code, 1)
        self.assertTrue(err)
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        other = self.new("Keep me")
        code, _, _ = self.run_cli("delete", nid)
        self.assertEqual(code, 0)
        self.assertFalse(path.exists())
        self.assertTrue((self.dir / f"{other}.md").exists())
        for cmd in ("show", "edit", "delete"):
            code, out, err = self.run_cli(cmd, "missing")
            self.assertEqual(code, 1)
            self.assertTrue(err)
            self.assertEqual(out, "")
        code, _, err = self.run_cli("show", "../evil")
        self.assertEqual(code, 1)

    def test_stdlib_only_imports(self):
        src = (ROOT / "note_taker.py").read_text(encoding="utf-8")
        std = {"argparse", "datetime", "os", "re", "shlex", "subprocess", "sys", "pathlib"}
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            else:
                continue
            for m in mods:
                self.assertIn(m.split(".")[0], std, m)
        self.assertEqual([p.name for p in ROOT.glob("note_taker*.py")], ["note_taker.py"])


if __name__ == "__main__":
    unittest.main()
