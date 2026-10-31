"""Black-box probes for mini-OS. Usage: python3 -I run_probes.py <side> <srcdir> <outjson>"""
import json, os, re, shutil, subprocess, sys, tempfile, time

side, src, out = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]
# Invocation adaptation only: image path and drive type from each side's own `make run`.
CFG = {"A": {"img": "build/os.img", "drive": "format=raw,if=floppy"},
       "B": {"img": "os.img", "drive": "format=raw"}}[side]
res, log = {}, {}
tmp = tempfile.mkdtemp()
work = os.path.join(tmp, "w")
shutil.copytree(src, work)
subprocess.run(["make", "clean"], cwd=work, capture_output=True)

b = subprocess.run(["make"], cwd=work, capture_output=True, text=True)
log["build"] = b.stdout[-2000:] + b.stderr[-2000:]
img = os.path.join(work, CFG["img"])
res["P1_build_from_clean"] = "pass" if b.returncode == 0 and os.path.exists(img) else "fail"

def qemu_dump(cmds, wait=4, extra=()):
    p = subprocess.Popen(["qemu-system-i386", "-display", "none", "-monitor", "stdio", "-no-reboot",
                          "-drive", f"{CFG['drive']},file={img}", *extra],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(wait)
    alive = p.poll() is None
    try:
        o, e = p.communicate("\n".join(cmds) + "\nquit\n", timeout=30)
    except subprocess.TimeoutExpired:
        p.kill(); o, e = p.communicate()
    return alive, o, e

def vga_text(o, start=0):
    vals = []
    for line in re.findall(r"^[0-9a-f]+:((?: 0x[0-9a-f]{2})+)\s*$", o, re.M):
        vals += [int(x, 16) for x in line.split()]
    return bytes(vals[0::2]).decode("ascii", "replace"), vals

if os.path.exists(img):
    data = open(img, "rb").read()
    res["P2_boot_sector_signature"] = "pass" if len(data) >= 512 and data[510:512] == b"\x55\xaa" else "fail"
    res["P3_image_has_kernel_after_bootsector"] = "pass" if len(data) > 512 and any(data[512:]) else "fail"
    res["P4_image_minimal_lt_2MiB"] = "pass" if len(data) <= 2 * 1024 * 1024 else "fail"
    kbytes = len(data[512:].rstrip(b"\0"))
    log["kernel_payload_bytes"] = kbytes
    alive, o, e = qemu_dump(["xp /4000bx 0xb8000", "info registers"], wait=4)
    text, vals = vga_text(o)
    log["vga_text"] = text
    log["qemu_err"] = e[-500:]
    nonblank = text.replace(" ", "").replace("\0", "")
    res["P5_qemu_boots_and_stays_up"] = "pass" if alive else "fail"
    # banner: kernel-written text (not SeaBIOS) at top of screen
    res["P6_vga_text_output_from_kernel"] = "pass" if ("SeaBIOS" not in text and len(nonblank) >= 10) else "fail"
    attrs = set(vals[1::2])
    res["P7_vga_attribute_bytes_set"] = "pass" if attrs and attrs != {0} else "fail"
    m = re.search(r"CR0=([0-9a-f]+)", o)
    log["cr0"] = m.group(1) if m else None
    res["P8_cpu_in_protected_mode"] = "pass" if m and int(m.group(1), 16) & 1 else "fail"
    m2 = re.search(r"EIP=([0-9a-f]+)", o)
    log["eip"] = m2.group(1) if m2 else None
    res["P9_executing_outside_bios_rom"] = "pass" if m2 and int(m2.group(1), 16) < 0xA0000 else "fail"
    # stability: still alive after longer time with -no-reboot (no triple fault)
    alive2, o2, _ = qemu_dump(["xp /160bx 0xb8000"], wait=10)
    t2, _ = vga_text(o2)
    res["P10_stable_after_10s_no_reset"] = "pass" if alive2 and t2[:80] == text[:80] else "fail"
else:
    for k in ["P2_boot_sector_signature", "P3_image_has_kernel_after_bootsector", "P4_image_minimal_lt_2MiB",
              "P5_qemu_boots_and_stays_up", "P6_vga_text_output_from_kernel", "P7_vga_attribute_bytes_set",
              "P8_cpu_in_protected_mode", "P9_executing_outside_bios_rom", "P10_stable_after_10s_no_reset"]:
        res[k] = "fail"

# P11: freestanding: no #include of non-freestanding headers, kernel link has no undefined symbols
inc_ok = True
for root, _, files in os.walk(work):
    for f in files:
        if f.endswith((".c", ".h")):
            for inc in re.findall(r'#\s*include\s*[<"]([^>"]+)[>"]', open(os.path.join(root, f)).read()):
                if inc not in {"stdint.h", "stddef.h", "stdbool.h", "stdarg.h", "limits.h", "float.h"}:
                    inc_ok = False; log.setdefault("bad_includes", []).append(inc)
objs = [os.path.join(r, f) for r, _, fs in os.walk(work) for f in fs if f.endswith(".o")]
undef = []
for ob in objs:
    nm = subprocess.run(["i686-elf-nm", "-u", ob], capture_output=True, text=True).stdout.split()
    undef += [s for s in nm if s not in ("U",)]
undef = sorted(set(undef) - {"kmain"})
log["undefined_symbols"] = undef
res["P11_no_external_libraries"] = "pass" if inc_ok and objs and not undef else "fail"
# P12: boot sector is own code assembled by nasm (512 bytes) present in repo
asm = [f for r, _, fs in os.walk(work) for f in fs if f.endswith(".asm")]
bins = [os.path.join(r, f) for r, _, fs in os.walk(work) for f in fs if f == "boot.bin"]
res["P12_own_bootloader_512B"] = "pass" if asm and bins and os.path.getsize(bins[0]) == 512 else "fail"
# P13: rebuild idempotent (make twice succeeds)
b2 = subprocess.run(["make"], cwd=work, capture_output=True, text=True)
res["P13_rebuild_succeeds"] = "pass" if b2.returncode == 0 else "fail"
# P14: make clean removes the image
subprocess.run(["make", "clean"], cwd=work, capture_output=True)
res["P14_clean_removes_image"] = "pass" if not os.path.exists(img) else "fail"
shutil.rmtree(tmp)
json.dump({"results": res, "log": log}, open(out, "w"), indent=1)
print(json.dumps(res, indent=1)); print(json.dumps(log, indent=1)[:3000])
