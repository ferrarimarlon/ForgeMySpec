import os
import re
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "os", "build")
IMG = os.path.join(BUILD, "os.img")
BANNER = "MiniOS 0.1"


def read(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return f.read()


class OsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["make", "-C", ROOT, "all"], check=True, capture_output=True)

    def test_boot_sector_signature(self):
        with open(IMG, "rb") as f:
            img = f.read()
        self.assertGreater(len(img), 512)
        self.assertEqual(img[510:512], b"\x55\xaa")
        with open(os.path.join(BUILD, "boot.bin"), "rb") as f:
            self.assertEqual(len(f.read()), 512)

    def test_kernel_is_freestanding(self):
        src = read("os/kernel.c").decode()
        self.assertEqual(re.findall(r"#\s*include\s*[<\"][^>\"]+", src), [])
        mk = read("Makefile").decode()
        self.assertIn("-ffreestanding", mk)
        self.assertIn("-nostdlib", mk)
        out = subprocess.run(["i686-elf-nm", "-u", os.path.join(BUILD, "kernel.elf")],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip(), "")

    def test_kernel_uses_vga_buffer(self):
        src = read("os/kernel.c").decode()
        self.assertIn("0xB8000", src)
        self.assertIn("VGA_COLS  80", src)
        self.assertIn("VGA_ROWS  25", src)

    def test_qemu_boot_shows_banner(self):
        with tempfile.TemporaryDirectory() as d:
            dump = os.path.join(d, "vga.bin")
            p = subprocess.Popen(
                ["qemu-system-i386", "-display", "none", "-serial", "none",
                 "-monitor", "stdio", "-drive", "format=raw,file=" + IMG],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                text = ""
                for _ in range(10):
                    time.sleep(1)
                    if os.path.exists(dump):
                        os.remove(dump)
                    p.stdin.write(("pmemsave 0xb8000 4000 \"%s\"\n" % dump).encode())
                    p.stdin.flush()
                    time.sleep(0.5)
                    if os.path.exists(dump):
                        with open(dump, "rb") as f:
                            text = f.read()[0::2].decode("latin1")
                        if BANNER in text:
                            break
            finally:
                p.kill()
                p.wait()
            self.assertIn(BANNER, text)


if __name__ == "__main__":
    unittest.main()
