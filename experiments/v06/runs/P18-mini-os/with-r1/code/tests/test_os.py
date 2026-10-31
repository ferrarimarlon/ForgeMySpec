import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
BANNER = "MiniOS kernel loaded"


def build():
    subprocess.run(["make", "-C", str(ROOT)], check=True, capture_output=True)


class BootSectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()

    def test_boot_sector_is_512_bytes_with_signature(self):
        data = (BUILD / "boot.bin").read_bytes()
        self.assertEqual(len(data), 512)
        self.assertEqual(data[-2:], b"\x55\xaa")

    def test_image_holds_kernel_after_boot_sector(self):
        img = (BUILD / "os.img").read_bytes()
        kernel = (BUILD / "kernel.bin").read_bytes()
        self.assertGreater(len(kernel), 0)
        self.assertEqual(img[512:512 + len(kernel)], kernel)
        src = (ROOT / "boot" / "boot.asm").read_text().lower()
        for needle in ("lgdt", "cr0", "jmp code_seg"):
            self.assertIn(needle, src)


class KernelSourceTests(unittest.TestCase):
    def test_vga_driver_present(self):
        src = (ROOT / "kernel" / "kernel.c").read_text()
        self.assertIn("0xB8000", src)
        for fn in ("clear", "putc", "puts", "newline", "scroll"):
            self.assertRegex(src, r"\b%s\s*\(" % fn)

    def test_no_external_libraries(self):
        allowed = {"stdint.h", "stddef.h", "stdbool.h", "stdarg.h", "limits.h", "float.h"}
        for path in list((ROOT / "kernel").glob("*.[ch]")):
            for inc in re.findall(r'#\s*include\s*[<"]([^>"]+)[>"]', path.read_text()):
                self.assertIn(inc, allowed, f"{path.name} includes {inc}")
        mk = (ROOT / "Makefile").read_text()
        self.assertIn("-ffreestanding", mk)
        self.assertIn("-nostdlib", mk)


@unittest.skipUnless(shutil.which("qemu-system-i386"), "qemu-system-i386 not installed")
class QemuBootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()

    def test_banner_in_vga_memory(self):
        proc = subprocess.Popen(
            ["qemu-system-i386", "-display", "none", "-monitor", "stdio",
             "-drive", f"format=raw,if=floppy,file={BUILD / 'os.img'}"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            time.sleep(4)
            out, _ = proc.communicate("xp /128bx 0xb8000\nquit\n", timeout=20)
        finally:
            if proc.poll() is None:
                proc.kill()
        vals = []
        for line in re.findall(r"^[0-9a-f]{16}:((?: 0x[0-9a-f]{2})+)$", out, re.M):
            vals += [int(x, 16) for x in line.split()]
        text = bytes(vals[0::2]).decode("ascii", "replace")
        self.assertTrue(text.startswith(BANNER), text)


if __name__ == "__main__":
    unittest.main()
