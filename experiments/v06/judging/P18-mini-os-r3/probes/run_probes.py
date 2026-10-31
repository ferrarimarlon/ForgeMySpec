import json, os, re, shutil, subprocess, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDES = {"A": {"img": "build/os.img", "boot": "build/boot.bin"},
         "B": {"img": "os.img", "boot": "boot.bin"}}

def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)

def vga_text(img, delay=2.0, keys=()):
    p = subprocess.Popen(["qemu-system-i386", "-display", "none", "-monitor", "stdio",
                          "-serial", "none", "-drive", "format=raw,file=" + img],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    time.sleep(delay)
    cmds = "".join("sendkey %s\n" % k for k in keys) + "xp /4000bx 0xb8000\ninfo registers\nquit\n"
    try:
        out, _ = p.communicate(cmds, timeout=30)
    finally:
        if p.poll() is None: p.kill()
    vals = []
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{16}): (.*)$", line.strip())
        if m: vals += [int(x, 16) for x in re.findall(r"0x([0-9a-f]{2})", m.group(2))]
    return bytes(vals[0::2]).decode("ascii", "replace"), bytes(vals[1::2]), out

def probe(side):
    res, log = {}, {}
    tmp = tempfile.mkdtemp()
    d = os.path.join(tmp, side)
    shutil.copytree(os.path.join(ROOT, side), d)
    s = SIDES[side]
    sh(["make", "clean"], d)
    r = sh(["make"], d)
    img = os.path.join(d, s["img"])
    res["P1_clean_build"] = "pass" if r.returncode == 0 and os.path.exists(img) else "fail"
    log["P1"] = (r.stdout + r.stderr)[-800:]
    bb = open(os.path.join(d, s["boot"]), "rb").read() if os.path.exists(os.path.join(d, s["boot"])) else b""
    data = open(img, "rb").read() if os.path.exists(img) else b""
    res["P2_boot_sector_512_sig"] = "pass" if len(bb) == 512 and data[510:512] == b"\x55\xaa" else "fail"
    res["P3_kernel_after_bootsector"] = "pass" if len(data) > 512 and any(data[512:1024]) else "fail"
    # freestanding / no external libs: no hosted includes, no -l flags, no undefined syms in objects
    srcs = []
    for dp, _, fs in os.walk(d):
        srcs += [os.path.join(dp, f) for f in fs if f.endswith((".c", ".h"))]
    hosted = [f for f in srcs if re.search(r"#\s*include\s*<", open(f).read())]
    mk = open(os.path.join(d, "Makefile")).read()
    ok = not hosted and "-ffreestanding" in mk and not any(re.search(r"(?<!\S)-l\w", l) for l in mk.splitlines() if "$(LD)" in l or "$(CC)" in l)
    res["P4_no_external_libs"] = "pass" if ok else "fail"
    log["P4"] = hosted
    # undefined symbols resolved only internally: link succeeded with -nostdlib-ish -> check nm of objects
    objs = []
    for dp, _, fs in os.walk(d):
        objs += [os.path.join(dp, f) for f in fs if f.endswith(".o")]
    undef = set(); defined = set()
    for o in objs:
        out = sh(["i686-elf-nm", o], d).stdout
        for l in out.splitlines():
            parts = l.split()
            if len(parts) == 2 and parts[0] == "U": undef.add(parts[1])
            elif len(parts) == 3: defined.add(parts[2])
    res["P5_no_unresolved_external_symbols"] = "pass" if objs and undef <= defined else "fail"
    log["P5"] = sorted(undef - defined)
    res["P6_image_small_le_1MiB"] = "pass" if 0 < len(data) <= 1024 * 1024 else "fail"
    log["size"] = len(data)
    text, attrs, mon = vga_text(img)
    log["vga"] = text[:400]
    res["P7_qemu_boots_vga_text"] = "pass" if re.search(r"[A-Za-z]{4,}.*[A-Za-z]{4,}", text[:160]) and "Disk error" not in text else "fail"
    res["P8_vga_attribute_bytes_set"] = "pass" if any(a != 0 for a in attrs[:80]) else "fail"
    m = re.search(r"CR0=([0-9a-f]+)", mon)
    res["P9_protected_mode_reached"] = "pass" if m and int(m.group(1), 16) & 1 else "fail"
    m = re.search(r"EIP=([0-9a-f]+)", mon)
    log["eip"] = m.group(1) if m else None
    # stability: still showing banner after longer run (no triple fault / reboot loop)
    text2, _, _ = vga_text(img, delay=5.0)
    res["P10_stable_after_5s"] = "pass" if text2[:160] == text[:160] and text[:20].strip() else "fail"
    # boot from a copy of image in a different directory (self-contained)
    alt = os.path.join(tmp, "copy.img"); shutil.copy(img, alt)
    t3, _, _ = vga_text(alt)
    res["P11_image_self_contained"] = "pass" if t3[:160] == text[:160] else "fail"
    readme = os.path.join(d, "README.md")
    res["P12_documented_build_run"] = "pass" if os.path.exists(readme) and "qemu" in open(readme).read().lower() and "run:" in mk else "fail"
    shutil.rmtree(tmp)
    return res, log

out, logs = {}, {}
for side in ("A", "B"):
    out[side], logs[side] = probe(side)
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
json.dump(logs, open(os.path.join(ROOT, "probes", "log.json"), "w"), indent=1)
print(json.dumps(out, indent=1)); print(json.dumps(logs, indent=1))
