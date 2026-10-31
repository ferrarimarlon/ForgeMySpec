import json, os, subprocess, sys, tempfile, time, ast
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STDLIB = set(sys.stdlib_module_names)  # requires python>=3.10

def w(p, s="x"):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(s)

def run(side, d, *args, timeout=20):
    return subprocess.run([sys.executable, os.path.join(HERE, side, "organizer.py"), d, *args],
                          capture_output=True, text=True, timeout=timeout)

def probes(side):
    r = {}
    src = os.path.join(HERE, side, "organizer.py")
    r["P01_single_file"] = os.path.isfile(src)
    tree = ast.parse(open(src).read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    r["P02_stdlib_only"] = mods <= STDLIB
    with tempfile.TemporaryDirectory() as d:
        w(f"{d}/a.txt"); w(f"{d}/b.PDF"); w(f"{d}/c.jpg"); w(f"{d}/README")
        p = run(side, d, "--once")
        r["P03_once_exit0"] = p.returncode == 0
        r["P04_moves_by_ext"] = os.path.isfile(f"{d}/txt/a.txt") and os.path.isfile(f"{d}/jpg/c.jpg") and not os.path.exists(f"{d}/a.txt")
        r["P05_uppercase_ext"] = any(os.path.isfile(f"{d}/{x}/b.PDF") for x in ("pdf", "PDF"))
        r["P06_noext_handled"] = p.returncode == 0 and any(os.path.isfile(os.path.join(d, x, "README")) for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)))
        log = f"{d}/organizer.log"
        txt = open(log).read() if os.path.exists(log) else ""
        r["P07_log_written"] = all(n in txt for n in ("a.txt", "c.jpg"))
        r["P08_log_not_moved"] = os.path.isfile(log) and not os.path.exists(f"{d}/log/organizer.log")
    with tempfile.TemporaryDirectory() as d:
        w(f"{d}/.hidden.txt"); w(f"{d}/.env")
        run(side, d, "--once")
        r["P09_skip_hidden"] = os.path.isfile(f"{d}/.hidden.txt") and os.path.isfile(f"{d}/.env")
    with tempfile.TemporaryDirectory() as d:
        w(f"{d}/sub/inner.txt"); w(f"{d}/pdf/x.txt"); w(f"{d}/sub/deep/y.md")
        run(side, d, "--once")
        r["P10_skip_subdir_files"] = os.path.isfile(f"{d}/sub/inner.txt") and os.path.isfile(f"{d}/pdf/x.txt") and os.path.isfile(f"{d}/sub/deep/y.md") and not os.path.exists(f"{d}/txt")
    with tempfile.TemporaryDirectory() as d:
        w(f"{d}/txt/a.txt", "old"); w(f"{d}/a.txt", "new")
        run(side, d, "--once")
        files = sorted(os.listdir(f"{d}/txt"))
        contents = sorted(open(f"{d}/txt/{f}").read() for f in files)
        r["P11_collision_no_loss"] = contents == ["new", "old"]
    with tempfile.TemporaryDirectory() as d:
        w(f"{d}/a.txt")
        run(side, d, "--once"); run(side, d, "--once")
        r["P12_idempotent"] = os.listdir(f"{d}/txt") == ["a.txt"]
    # arbitrary common extensions should all be organized
    with tempfile.TemporaryDirectory() as d:
        for n in ("x.tmp", "y.part", "z.py", "organizer.py"):
            w(f"{d}/{n}")
        run(side, d, "--once")
        r["P13a_tmp_part_files_moved"] = not os.path.exists(f"{d}/x.tmp") and not os.path.exists(f"{d}/y.part")
        r["P13b_user_organizer_py_moved"] = not os.path.exists(f"{d}/organizer.py") and not os.path.exists(f"{d}/z.py")
    with tempfile.TemporaryDirectory() as d:
        p = run(side, os.path.join(d, "nope"), "--once")
        r["P14_missing_dir_error"] = p.returncode != 0 and "Traceback" not in p.stderr
    with tempfile.TemporaryDirectory() as d:
        p = run(side, d)
        r["P15_mode_required"] = p.returncode != 0
    with tempfile.TemporaryDirectory() as d:
        w(f"{d}/pre.txt")
        proc = subprocess.Popen([sys.executable, os.path.join(HERE, side, "organizer.py"), d, "--watch", "--interval", "0.2"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.5)
            w(f"{d}/new.csv"); w(f"{d}/.h.csv")
            ok = False
            for _ in range(50):
                if os.path.isfile(f"{d}/csv/new.csv") and os.path.isfile(f"{d}/txt/pre.txt"):
                    ok = True; break
                time.sleep(0.1)
            r["P16_watch_moves_new"] = ok and proc.poll() is None
            r["P17_watch_skips_hidden"] = os.path.isfile(f"{d}/.h.csv")
            txt = open(f"{d}/organizer.log").read() if os.path.exists(f"{d}/organizer.log") else ""
            r["P18_watch_logs"] = "new.csv" in txt
        finally:
            proc.terminate(); proc.wait(5)
    return {k: ("pass" if v else "fail") for k, v in r.items()}

res = {s: probes(s) for s in ("A", "B")}
json.dump(res, open(os.path.join(HERE, "probes", "results.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
