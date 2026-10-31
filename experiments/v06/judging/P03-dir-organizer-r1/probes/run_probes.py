import json, os, subprocess, sys, tempfile, time, ast, signal
PY = "/opt/homebrew/bin/python3.11"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def prog(side): return os.path.join(HERE, side, "organizer.py")
def touch(p, t="x"):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(t)
def run(side, d, *args, cwd=None):
    return subprocess.run([PY, "-I", prog(side), d, *args], capture_output=True, text=True, cwd=cwd or d, timeout=30)
def logtext(d, cwd):
    s = ""
    for p in (os.path.join(d, "organizer.log"), os.path.join(cwd, "organizer.log")):
        if os.path.exists(p): s += open(p).read()
    return s
def env():
    t = tempfile.mkdtemp(); d = os.path.join(t, "target"); c = os.path.join(t, "cwd"); os.makedirs(d); os.makedirs(c); return d, c
P = {}
def probe(f): P[f.__name__] = f; return f

@probe
def P01_once_moves_by_ext(side):
    d, c = env()
    for n in ("a.txt", "b.jpg", "c.PDF"): touch(os.path.join(d, n))
    r = run(side, d, "--once", cwd=c)
    return r.returncode == 0 and all(os.path.isfile(os.path.join(d, x, y)) for x, y in (("txt","a.txt"),("jpg","b.jpg"),("pdf","c.PDF")))
@probe
def P02_once_exits(side):
    d, c = env(); touch(os.path.join(d, "a.txt"))
    try: r = run(side, d, "--once", cwd=c); return r.returncode == 0
    except subprocess.TimeoutExpired: return False
@probe
def P03_log_records_move(side):
    d, c = env(); touch(os.path.join(d, "report.txt"))
    run(side, d, "--once", cwd=c)
    return "report.txt" in logtext(d, c)
@probe
def P04_log_in_cwd_is_target_not_moved(side):
    d, c = env(); touch(os.path.join(d, "a.txt"))
    run(side, d, "--once", cwd=d); run(side, d, "--once", cwd=d)
    return os.path.isfile(os.path.join(d, "organizer.log")) and not os.path.exists(os.path.join(d, "log"))
@probe
def P05_skip_subdir_files(side):
    d, c = env(); touch(os.path.join(d, "sub", "x.txt"))
    run(side, d, "--once", cwd=c)
    return os.path.isfile(os.path.join(d, "sub", "x.txt")) and not os.path.exists(os.path.join(d, "txt"))
@probe
def P06_skip_hidden(side):
    d, c = env(); touch(os.path.join(d, ".hidden.txt")); touch(os.path.join(d, ".bashrc"))
    run(side, d, "--once", cwd=c)
    return os.path.isfile(os.path.join(d, ".hidden.txt")) and os.path.isfile(os.path.join(d, ".bashrc"))
@probe
def P07_no_extension(side):
    d, c = env(); touch(os.path.join(d, "README"))
    r = run(side, d, "--once", cwd=c)
    return r.returncode == 0 and "Traceback" not in r.stderr and not os.path.isfile(os.path.join(d, "README")) or (r.returncode == 0 and os.path.isfile(os.path.join(d, "README")))
@probe
def P08_collision_no_overwrite(side):
    d, c = env(); touch(os.path.join(d, "txt", "a.txt"), "old"); touch(os.path.join(d, "a.txt"), "new")
    run(side, d, "--once", cwd=c)
    contents = sorted(open(os.path.join(d, "txt", f)).read() for f in os.listdir(os.path.join(d, "txt")))
    return contents == ["new", "old"]
@probe
def P09_watch_moves_new_file(side):
    d, c = env()
    p = subprocess.Popen([PY, "-I", prog(side), d, "--watch", "--interval", "0.2"], cwd=c, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(0.5); touch(os.path.join(d, "new.txt"))
        ok = False
        for _ in range(50):
            if os.path.isfile(os.path.join(d, "txt", "new.txt")): ok = True; break
            time.sleep(0.1)
        alive = p.poll() is None
    finally:
        p.send_signal(signal.SIGINT)
        try: p.wait(5)
        except subprocess.TimeoutExpired: p.kill()
    return ok and alive and "new.txt" in logtext(d, c)
@probe
def P10_watch_clean_sigint(side):
    d, c = env()
    p = subprocess.Popen([PY, "-I", prog(side), d, "--watch", "--interval", "0.2"], cwd=c, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.6); p.send_signal(signal.SIGINT)
    try: out, err = p.communicate(timeout=5)
    except subprocess.TimeoutExpired: p.kill(); return False
    return "Traceback" not in err
@probe
def P11_requires_mode(side):
    d, c = env()
    return run(side, d, cwd=c).returncode != 0 and run(side, d, "--once", "--watch", cwd=c).returncode != 0
@probe
def P12_bad_dir_error(side):
    d, c = env()
    r = run(side, os.path.join(d, "nope"), "--once", cwd=c)
    return r.returncode != 0 and "Traceback" not in r.stderr
@probe
def P13_single_file_stdlib(side):
    py = [f for f in os.listdir(os.path.join(HERE, side)) if f.endswith(".py")]
    tree = ast.parse(open(prog(side)).read()); mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    return py == ["organizer.py"] and mods <= set(sys.stdlib_module_names)
@probe
def P14_dest_name_clash_with_file(side):
    # top-level file 'pdf' (no ext) exists while 'x.pdf' needs folder 'pdf': must not crash, other files still processed
    d, c = env(); touch(os.path.join(d, "pdf"), "f"); touch(os.path.join(d, "x.pdf")); touch(os.path.join(d, "z.txt"))
    r = run(side, d, "--once", cwd=c)
    return "Traceback" not in r.stderr and os.path.isfile(os.path.join(d, "txt", "z.txt"))
@probe
def P15_symlink_not_followed_or_crash(side):
    d, c = env(); t = os.path.join(os.path.dirname(d), "outside.txt"); touch(t)
    os.symlink(t, os.path.join(d, "link.txt"))
    r = run(side, d, "--once", cwd=c)
    return r.returncode == 0 and os.path.isfile(t)
@probe
def P16_tmp_file_moved_by_ext(side):
    # spec says move all files by extension; .tmp is a regular extension
    d, c = env(); touch(os.path.join(d, "data.tmp"))
    run(side, d, "--once", cwd=c)
    return os.path.isfile(os.path.join(d, "tmp", "data.tmp"))

@probe
def P17_file_named_like_dest_dir(side):
    # top-level extensionless file 'no_extension' collides with its own destination dir; must not crash, others processed
    d, c = env(); touch(os.path.join(d, "no_extension"), "f"); touch(os.path.join(d, "z.txt"))
    r = run(side, d, "--once", cwd=c)
    return "Traceback" not in r.stderr and os.path.isfile(os.path.join(d, "txt", "z.txt")) and os.path.isfile(os.path.join(d, "no_extension"))

res = {}
for side in ("A", "B"):
    res[side] = {}
    for k, f in P.items():
        try: res[side][k] = "pass" if f(side) else "fail"
        except Exception as e: res[side][k] = "fail"; print(side, k, repr(e))
json.dump(res, open(os.path.join(HERE, "probes", "results.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
