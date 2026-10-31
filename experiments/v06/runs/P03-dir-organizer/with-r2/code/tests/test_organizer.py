import ast
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import organizer  # noqa: E402

SCRIPT = ROOT / "organizer.py"


def touch(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        self.target = self.root / "target"
        self.target.mkdir()
        self.log = self.root / "organizer.log"


class OrganizeTests(TmpCase):
    def test_moves_by_extension(self):
        touch(self.target / "a.TXT")
        touch(self.target / "b.pdf")
        touch(self.target / "README")
        touch(self.target / "x.tar.gz")
        organizer.organize_once(self.target, self.log)
        self.assertTrue((self.target / "txt" / "a.TXT").exists())
        self.assertTrue((self.target / "pdf" / "b.pdf").exists())
        self.assertTrue((self.target / "no_extension" / "README").exists())
        self.assertTrue((self.target / "gz" / "x.tar.gz").exists())
        # collision never overwrites
        touch(self.target / "a.TXT", "new")
        organizer.organize_once(self.target, self.log)
        self.assertEqual((self.target / "txt" / "a.TXT").read_text(), "x")
        self.assertEqual((self.target / "txt" / "a_1.TXT").read_text(), "new")

    def test_skips_files_in_subdirs(self):
        touch(self.target / "sub" / "deep.txt")
        touch(self.target / "sub" / "deeper" / "z.md")
        organizer.organize_once(self.target, self.log)
        self.assertTrue((self.target / "sub" / "deep.txt").exists())
        self.assertTrue((self.target / "sub" / "deeper" / "z.md").exists())
        self.assertFalse((self.target / "txt").exists())
        self.assertFalse((self.target / "md").exists())

    def test_skips_hidden_files(self):
        touch(self.target / ".hidden.txt")
        touch(self.target / ".env")
        organizer.organize_once(self.target, self.log)
        self.assertTrue((self.target / ".hidden.txt").exists())
        self.assertTrue((self.target / ".env").exists())
        self.assertFalse((self.target / "txt").exists())


class LogTests(TmpCase):
    def test_move_is_logged(self):
        touch(self.target / "a.txt")
        rc = organizer.main([str(self.target), "--once", "--log", str(self.log)])
        self.assertEqual(rc, 0)
        lines = self.log.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn(str(self.target / "a.txt"), lines[0])
        self.assertIn(str(self.target / "txt" / "a.txt"), lines[0])
        self.assertRegex(lines[0], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_log_inside_target_is_not_moved(self):
        log = self.target / "organizer.log"
        touch(self.target / "a.txt")
        organizer.main([str(self.target), "--once", "--log", str(log)])
        self.assertTrue(log.exists())
        self.assertFalse((self.target / "log").exists())


class WatchTests(TmpCase):
    def test_watch_organizes_new_files(self):
        stop = threading.Event()
        t = threading.Thread(
            target=organizer.watch,
            args=(self.target, self.log, 0.05, stop.is_set),
        )
        t.start()
        try:
            touch(self.target / "late.csv")
            dest = self.target / "csv" / "late.csv"
            deadline = time.time() + 5
            while time.time() < deadline and not dest.exists():
                time.sleep(0.05)
            self.assertTrue(dest.exists())
        finally:
            stop.set()
            t.join(5)
        self.assertFalse(t.is_alive())


class CliTests(TmpCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, cwd=self.root, timeout=30,
        )

    def test_once_exits_zero(self):
        touch(self.target / "a.txt")
        r = self.run_cli(str(self.target), "--once")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.target / "txt" / "a.txt").exists())
        self.assertTrue((self.root / "organizer.log").exists())

    def test_invalid_target_exits_two(self):
        r = self.run_cli(str(self.root / "missing"), "--once")
        self.assertEqual(r.returncode, 2)

    def test_mode_is_required_and_exclusive(self):
        self.assertNotEqual(self.run_cli(str(self.target)).returncode, 0)
        self.assertNotEqual(self.run_cli(str(self.target), "--once", "--watch").returncode, 0)

    def test_single_file_script_runs(self):
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--watch", r.stdout)
        self.assertIn("--once", r.stdout)

    def test_imports_are_stdlib_only(self):
        tree = ast.parse(SCRIPT.read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add(node.module.split(".")[0])
        self.assertTrue(names)
        import importlib.util
        import sysconfig
        stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
        for name in names:
            spec = importlib.util.find_spec(name)
            self.assertIsNotNone(spec, name)
            origin = spec.origin
            if origin in (None, "built-in", "frozen"):
                continue
            real = os.path.realpath(origin)
            self.assertTrue(real.startswith(stdlib) and "site-packages" not in real, name)


if __name__ == "__main__":
    unittest.main()
