import json, os, re, shutil, subprocess, sys, tempfile, time, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIDES = {"A": "os/build/os.img", "B": "os.img"}

def boot_text(img, qemu="qemu-system-i386", drive="format=raw,file=%s", wait=4):
    with tempfile.TemporaryDirectory() as d:
        dump = os.path.join(d, "v.bin")
        p = subprocess.Popen([qemu, "-display", "none", "-serial", "none", "-no-reboot",
                              "-monitor", "stdio", "-drive", drive % img],
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(wait)
        alive = p.poll() is None
        text = ""
        if alive:
            p.stdin.write(('pmemsave 0xb8000 4000 "%s"\n' % dump).encode()); p.stdin.flush()
            time.sleep(1)
            if os.path.exists(dump):
                text = open(dump, "rb").read()[0::2].decode("latin1")
        p.kill(); p.wait()
        return alive, text

res = {}
log = {}
for side, imgrel in SIDES.items():
    r = {}; L = {}
    work = tempfile.mkdtemp()
    src = os.path.join(work, side)
    shutil.copytree(os.path.join(ROOT, side), src)
    subprocess.run(["make", "-C", src, "clean"], capture_output=True)
    b = subprocess.run(["make", "-C", src], capture_output=True, text=True)
    img = os.path.join(src, imgrel)
    r["P01_clean_build"] = "pass" if b.returncode == 0 and os.path.exists(img) else "fail"
    L["P01"] = (b.stdout + b.stderr)[-600:]
    r["P02_no_warnings"] = "pass" if b.returncode == 0 and "warning" not in b.stderr.lower() else "fail"
    data = open(img, "rb").read() if os.path.exists(img) else b""
    r["P03_boot_signature"] = "pass" if len(data) > 512 and data[510:512] == b"\x55\xaa" else "fail"
    # freestanding: no includes in C sources, no undefined syms in objects
    cs = glob.glob(os.path.join(src, "**/*.c"), recursive=True)
    inc = any(re.search(r"#\s*include", open(c).read()) for c in cs)
    objs = glob.glob(os.path.join(src, "**/*.o"), recursive=True)
    und = set()
    defined = set()
    for o in objs:
        out = subprocess.run(["i686-elf-nm", o], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == "U": und.add(parts[1])
            elif len(parts) == 3: defined.add(parts[2])
    ext = und - defined
    L["P04"] = sorted(ext)
    r["P04_no_external_libs"] = "pass" if not inc and not ext and objs else "fail"
    r["P05_vga_b8000_in_source"] = "pass" if any("0xB8000" in open(c).read().upper().replace("0XB8000","0xB8000") for c in cs) else "fail"
    alive, t = boot_text(img)
    L["P06"] = t[:240]
    r["P06_qemu_i386_hdd_banner"] = "pass" if alive and "MiniOS" in t else "fail"
    alive, t = boot_text(img, drive="format=raw,if=floppy,file=%s")
    L["P07"] = t[:240]
    r["P07_qemu_i386_floppy_banner"] = "pass" if alive and "MiniOS" in t else "fail"
    alive, t = boot_text(img, qemu="qemu-system-x86_64")
    r["P08_qemu_x86_64_banner"] = "pass" if alive and "MiniOS" in t else "fail"
    alive, t = boot_text(img, wait=8)
    r["P09_stable_no_reset_8s"] = "pass" if alive and "MiniOS" in t else "fail"
    kb = glob.glob(os.path.join(src, "**/kernel.bin"), recursive=True)
    ksz = os.path.getsize(kb[0]) if kb else 10**9
    L["P10"] = ksz
    r["P10_minimal_kernel_le_16KiB"] = "pass" if ksz <= 16384 else "fail"
    n = subprocess.run(["make", "-n", "-C", src, "run"], capture_output=True, text=True)
    r["P11_make_run_qemu"] = "pass" if n.returncode == 0 and "qemu-system" in n.stdout else "fail"
    # bootloader is own code: boot.bin of 512 bytes built from asm
    bb = glob.glob(os.path.join(src, "**/boot.bin"), recursive=True)
    r["P12_own_bootloader_512"] = "pass" if bb and os.path.getsize(bb[0]) == 512 and glob.glob(os.path.join(src, "**/boot.asm"), recursive=True) else "fail"
    shutil.rmtree(work)
    res[side] = r; log[side] = L
json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1)
json.dump(log, open(os.path.join(HERE, "log.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1)); print(json.dumps(log, indent=1, default=str))
