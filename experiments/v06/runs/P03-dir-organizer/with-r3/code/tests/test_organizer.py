import ast
import os
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import organizer  # noqa: E402


def touch(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class OrganizerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def p(self, *parts):
        return os.path.join(self.d, *parts)

    def test_once_moves_by_extension(self):
        touch(self.p("a.txt"))
        touch(self.p("B.PDF"))
        touch(self.p("README"))
        touch(self.p("x.tar.gz"))
        rc = organizer.main([self.d, "--once"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(self.p("txt", "a.txt")))
        self.assertTrue(os.path.isfile(self.p("pdf", "B.PDF")))
        self.assertTrue(os.path.isfile(self.p("no_extension", "README")))
        self.assertTrue(os.path.isfile(self.p("gz", "x.tar.gz")))
        self.assertFalse(os.path.exists(self.p("a.txt")))

    def test_watch_organizes_new_files(self):
        stop = threading.Event()
        t = threading.Thread(target=organizer.watch, args=(self.d, 0.05, stop))
        t.start()
        try:
            time.sleep(0.15)
            touch(self.p("late.csv"))
            deadline = time.time() + 3
            while time.time() < deadline and not os.path.exists(self.p("csv", "late.csv")):
                time.sleep(0.05)
            self.assertTrue(t.is_alive())
            self.assertTrue(os.path.isfile(self.p("csv", "late.csv")))
        finally:
            stop.set()
            t.join(3)
        self.assertFalse(t.is_alive())

    def test_moves_logged(self):
        touch(self.p("a.txt"))
        organizer.main([self.d, "--once"])
        with open(self.p("organizer.log")) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
        self.assertIn("a.txt", lines[0])
        self.assertIn(os.path.join("txt", "a.txt"), lines[0])
        self.assertTrue(os.path.exists(self.p("organizer.log")))
        organizer.main([self.d, "--once"])  # log itself is never moved
        self.assertTrue(os.path.exists(self.p("organizer.log")))
        self.assertFalse(os.path.exists(self.p("log")))

    def test_skips_files_in_subdirs(self):
        touch(self.p("sub", "inner.txt"))
        touch(self.p("pdf", "old.txt"))
        organizer.main([self.d, "--once"])
        self.assertTrue(os.path.isfile(self.p("sub", "inner.txt")))
        self.assertTrue(os.path.isfile(self.p("pdf", "old.txt")))
        self.assertFalse(os.path.exists(self.p("txt")))
        self.assertFalse(os.path.exists(self.p("organizer.log")))

    def test_skips_hidden_files(self):
        touch(self.p(".secret.txt"))
        touch(self.p(".hidden"))
        organizer.main([self.d, "--once"])
        self.assertTrue(os.path.isfile(self.p(".secret.txt")))
        self.assertTrue(os.path.isfile(self.p(".hidden")))
        self.assertFalse(os.path.exists(self.p("txt")))

    def test_single_file_stdlib_only(self):
        with open(os.path.join(ROOT, "organizer.py")) as fh:
            tree = ast.parse(fh.read())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                mods.add(node.module.split(".")[0])
        self.assertTrue(mods)
        names = getattr(sys, "stdlib_module_names", None)
        if names is not None:
            self.assertEqual(mods - set(names), set())
            return
        import importlib.util
        import sysconfig
        stdlib = sysconfig.get_paths()["stdlib"]
        for m in mods:
            spec = importlib.util.find_spec(m)
            origin = getattr(spec, "origin", None)
            if origin in (None, "built-in", "frozen"):
                continue
            self.assertTrue(origin.startswith(stdlib), m)
            self.assertNotIn("site-packages", origin, m)

    def test_collision_not_overwritten(self):
        touch(self.p("txt", "a.txt"), "old")
        touch(self.p("a.txt"), "new")
        organizer.main([self.d, "--once"])
        with open(self.p("txt", "a.txt")) as fh:
            self.assertEqual(fh.read(), "old")
        with open(self.p("txt", "a_1.txt")) as fh:
            self.assertEqual(fh.read(), "new")


if __name__ == "__main__":
    unittest.main()
