import os, re, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "build", "os.img")


def read(path):
    with open(os.path.join(ROOT, path)) as f:
        return f.read()


def build():
    subprocess.run(["make", "-C", ROOT], check=True, capture_output=True)


class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()

    def test_boot_signature(self):
        with open(IMG, "rb") as f:
            sector = f.read(512)
        self.assertEqual(len(sector), 512)
        self.assertEqual(sector[510:512], b"\x55\xaa")
        self.assertEqual(os.path.getsize(os.path.join(ROOT, "build", "boot.bin")), 512)

    def test_protected_mode_and_kernel_elf(self):
        out = subprocess.run(["i686-elf-readelf", "-h", os.path.join(ROOT, "build", "kernel.elf")],
                             check=True, capture_output=True, text=True).stdout
        self.assertIn("ELF32", out)
        self.assertIn("Intel 80386", out)
        boot = read("boot/boot.asm")
        self.assertRegex(boot, r"or\s+eax,\s*1")
        self.assertRegex(boot, r"mov\s+cr0,\s*eax")
        self.assertRegex(boot, r"jmp\s+0x08:KERNEL_ADDR")


class SourceTests(unittest.TestCase):
    def test_vga_driver_uses_b8000(self):
        src = read("kernel/vga.c")
        self.assertIn("0xB8000", src)
        self.assertIn("attr", src)
        self.assertIn("'\\n'", src)
        self.assertIn("scroll", src)

    def test_freestanding_no_libs(self):
        mk = read("Makefile")
        self.assertIn("-ffreestanding", mk)
        self.assertIn("-nostdlib", mk)
        self.assertNotRegex(mk, r"(?<!\S)-l\w")
        for name in os.listdir(os.path.join(ROOT, "kernel")):
            if name.endswith((".c", ".h")):
                self.assertNotRegex(read("kernel/" + name), r"#\s*include\s*<",
                                    name + " includes a hosted header")


class BootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()

    def test_banner_in_vga_memory(self):
        import time
        p = subprocess.Popen(
            ["qemu-system-i386", "-display", "none", "-monitor", "stdio", "-serial", "none",
             "-drive", "format=raw,file=" + IMG],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            time.sleep(2)
            out, _ = p.communicate("xp /160bx 0xb8000\nquit\n", timeout=20)
        finally:
            if p.poll() is None:
                p.kill()
        # Dump lines look like "00000000000b8000: 0x4d 0x0a ..."; even bytes are characters.
        vals = []
        for line in out.splitlines():
            m = re.match(r"^([0-9a-f]{16}): (.*)$", line.strip())
            if m:
                vals += [int(x, 16) for x in re.findall(r"0x([0-9a-f]{2})", m.group(2))]
        text = bytes(vals[0::2]).decode("ascii", "replace")
        self.assertIn("MiniOS booted", text)


if __name__ == "__main__":
    unittest.main()
