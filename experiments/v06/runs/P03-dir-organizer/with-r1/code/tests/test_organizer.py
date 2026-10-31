import ast
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import organizer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_NAME = "organizer" + ".log"


def touch(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "target")
        os.makedirs(self.d)
        self.log = os.path.join(self._tmp.name, LOG_NAME)

    def p(self, *parts):
        return os.path.join(self.d, *parts)


class OrganizeTests(Base):
    def test_moves_by_extension(self):
        for n in ("a.txt", "b.PDF", "c", "d.tar.gz"):
            touch(self.p(n))
        organizer.organize(self.d)
        self.assertTrue(os.path.isfile(self.p("txt", "a.txt")))
        self.assertTrue(os.path.isfile(self.p("pdf", "b.PDF")))
        self.assertTrue(os.path.isfile(self.p("no_extension", "c")))
        self.assertTrue(os.path.isfile(self.p("gz", "d.tar.gz")))

    def test_collision_does_not_overwrite(self):
        touch(self.p("txt", "a.txt"), "old")
        touch(self.p("a.txt"), "new")
        organizer.organize(self.d)
        with open(self.p("txt", "a.txt")) as f:
            self.assertEqual(f.read(), "old")
        with open(self.p("txt", "a_1.txt")) as f:
            self.assertEqual(f.read(), "new")

    def test_move_is_logged(self):
        touch(self.p("a.txt"))
        logger = organizer.make_logger(self.log)
        organizer.organize(self.d, logger)
        for h in logger.handlers:
            h.flush()
        with open(self.log) as f:
            line = f.read()
        self.assertIn(self.p("a.txt"), line)
        self.assertIn(self.p("txt", "a.txt"), line)
        self.assertRegex(line, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")

    def test_skips_files_in_subdirs(self):
        touch(self.p("sub", "x.txt"))
        organizer.organize(self.d)
        self.assertTrue(os.path.isfile(self.p("sub", "x.txt")))
        self.assertFalse(os.path.exists(self.p("txt")))

    def test_skips_hidden_files(self):
        touch(self.p(".hidden.txt"))
        organizer.organize(self.d)
        self.assertTrue(os.path.isfile(self.p(".hidden.txt")))
        self.assertFalse(os.path.exists(self.p("txt")))


class CliTests(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "organizer.py"), *args],
                              capture_output=True, text=True, cwd=self._tmp.name)

    def test_once_exits_zero_and_moves(self):
        touch(self.p("a.txt"))
        r = self.run_cli(self.d, "--once")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.p("txt", "a.txt")))
        with open(self.log) as f:
            self.assertIn("a.txt", f.read())

    def test_invalid_arguments_rejected(self):
        self.assertNotEqual(self.run_cli(self.d).returncode, 0)
        self.assertNotEqual(self.run_cli(self.d, "--once", "--watch").returncode, 0)
        self.assertNotEqual(self.run_cli(os.path.join(self.d, "nope"), "--once").returncode, 0)


class WatchTests(Base):
    def test_watch_moves_new_file(self):
        done = threading.Event()
        t = threading.Thread(target=organizer.watch, kwargs=dict(
            target=self.d, interval=0.05, stop=done.is_set))
        t.start()
        try:
            touch(self.p("new.txt"))
            deadline = time.time() + 5
            while time.time() < deadline and not os.path.isfile(self.p("txt", "new.txt")):
                time.sleep(0.05)
            self.assertTrue(os.path.isfile(self.p("txt", "new.txt")))
        finally:
            done.set()
            t.join(5)
        self.assertFalse(t.is_alive())

    def test_watch_stops_on_interrupt(self):
        def boom(*a, **k):
            raise KeyboardInterrupt
        orig = organizer.organize
        organizer.organize = boom
        self.addCleanup(setattr, organizer, "organize", orig)
        organizer.watch(self.d, interval=0.01)


class StructureTests(unittest.TestCase):
    def test_single_file_stdlib_only(self):
        with open(os.path.join(ROOT, "organizer.py")) as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertTrue(mods)
        stdlib = {"argparse", "logging", "os", "shutil", "sys", "time"}
        self.assertLessEqual(mods, stdlib)
        py = [f for f in os.listdir(ROOT) if f.endswith(".py")]
        self.assertEqual(py, ["organizer.py"])


if __name__ == "__main__":
    unittest.main()
