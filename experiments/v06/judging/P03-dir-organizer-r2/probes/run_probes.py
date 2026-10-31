import ast, json, os, subprocess, sys, tempfile, time, signal
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent

def run(side, target, *args, cwd=None):
    script = HERE / side / "organizer.py"
    return subprocess.run([sys.executable, str(script), str(target), *args],
                          cwd=cwd or target, capture_output=True, text=True, timeout=30)

def mk(d, rel, content="x"):
    p = Path(d) / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content); return p

def p_once_basic(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"a.txt"); mk(d,"b.jpg"); mk(d,"c.py")
        r = run(side, d, "--once")
        return r.returncode==0 and all((Path(d)/e/f).is_file() for e,f in [("txt","a.txt"),("jpg","b.jpg"),("py","c.py")]) and not (Path(d)/"a.txt").exists()

def p_hidden(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,".secret.txt"); mk(d,".bashrc"); mk(d,"a.txt")
        r = run(side, d, "--once")
        return r.returncode==0 and (Path(d)/".secret.txt").is_file() and (Path(d)/".bashrc").is_file()

def p_subdir(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"docs/inner.txt"); mk(d,"x/y/deep.jpg")
        r = run(side, d, "--once")
        return r.returncode==0 and (Path(d)/"docs/inner.txt").is_file() and (Path(d)/"x/y/deep.jpg").is_file() and not (Path(d)/"txt").exists() and not (Path(d)/"jpg").exists()

def p_log_records(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"report.csv")
        r = run(side, d, "--once")
        lp = Path(d)/"organizer.log"
        return r.returncode==0 and lp.is_file() and "report.csv" in lp.read_text()

def p_log_not_moved(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"a.txt"); run(side, d, "--once"); mk(d,"b.txt"); r = run(side, d, "--once")
        return r.returncode==0 and (Path(d)/"organizer.log").is_file() and not (Path(d)/"log").exists()

def p_noext(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"README"); mk(d,"a.txt")
        r = run(side, d, "--once")
        return r.returncode==0 and (Path(d)/"txt/a.txt").is_file() and any(p.name=="README" for p in Path(d).rglob("README"))

def p_collision(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"txt/a.txt","old"); mk(d,"a.txt","new")
        r = run(side, d, "--once")
        contents = sorted(p.read_text() for p in (Path(d)/"txt").iterdir())
        return r.returncode==0 and contents==["new","old"] and not (Path(d)/"a.txt").exists()

def p_file_blocks_dir(side):
    # top-level file "txt" (no ext) blocks creation of dir txt/; must not abort the run
    with tempfile.TemporaryDirectory() as d:
        mk(d,"foo.txt"); mk(d,"txt","i am a file"); mk(d,"zz.jpg")
        r = run(side, d, "--once")
        return r.returncode==0 and (Path(d)/"jpg/zz.jpg").is_file() and "Traceback" not in r.stderr

def p_bad_dir(side):
    with tempfile.TemporaryDirectory() as d:
        r = run(side, Path(d)/"nope", "--once", cwd=d)
        return r.returncode!=0 and "Traceback" not in r.stderr

def p_mode_required(side):
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, str(HERE/side/"organizer.py"), d], cwd=d, capture_output=True, text=True, timeout=10)
        r2 = subprocess.run([sys.executable, str(HERE/side/"organizer.py"), d, "--once","--watch"], cwd=d, capture_output=True, text=True, timeout=10)
        return r.returncode!=0 and r2.returncode!=0

def p_idempotent(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"a.txt"); mk(d,"b.md"); run(side,d,"--once")
        snap = sorted(str(p.relative_to(d)) for p in Path(d).rglob("*") if p.name!="organizer.log")
        r = run(side,d,"--once")
        snap2 = sorted(str(p.relative_to(d)) for p in Path(d).rglob("*") if p.name!="organizer.log")
        return r.returncode==0 and snap==snap2

def p_watch_new_file(side):
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.Popen([sys.executable, str(HERE/side/"organizer.py"), d, "--watch", "--interval", "0.5"],
                             cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(1.5); mk(d,"new.pdf"); mk(d,".hid.pdf")
            ok=False
            for _ in range(40):
                if (Path(d)/"pdf/new.pdf").is_file(): ok=True; break
                time.sleep(0.25)
            time.sleep(1.5)
            alive = p.poll() is None
            hidden_ok = (Path(d)/".hid.pdf").is_file()
            logged = (Path(d)/"organizer.log").is_file() and "new.pdf" in (Path(d)/"organizer.log").read_text()
        finally:
            p.send_signal(signal.SIGINT)
            try: p.wait(5)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
        return ok and alive and hidden_ok and logged

def p_watch_sigint_clean(side):
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.Popen([sys.executable, str(HERE/side/"organizer.py"), d, "--watch", "--interval", "0.5"],
                             cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.5); p.send_signal(signal.SIGINT)
        try: out, err = p.communicate(timeout=5)
        except subprocess.TimeoutExpired: p.kill(); return False
        return p.returncode==0 and "Traceback" not in err

def p_stdlib_only(side):
    src = (HERE/side/"organizer.py").read_text()
    mods=set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    import importlib.util, sysconfig
    std = sysconfig.get_paths()['stdlib']
    def is_std(m):
        if m in sys.builtin_module_names: return True
        sp = importlib.util.find_spec(m)
        return sp is not None and sp.origin is not None and (sp.origin.startswith(std) or sp.origin=='built-in' or sp.origin=='frozen')
    return all(is_std(m) for m in mods)

def p_single_file(side):
    pys = [p for p in (HERE/side).rglob("*.py") if "tests" not in p.parts and "__pycache__" not in p.parts]
    return [p.name for p in pys]==["organizer.py"]

def p_relative_target(side):
    with tempfile.TemporaryDirectory() as d:
        mk(d,"t/a.txt")
        r = run(side, "t", "--once", cwd=d)
        return r.returncode==0 and (Path(d)/"t/txt/a.txt").is_file()

def p_tmp_ext_moved(side):
    # spec: every non-hidden top-level file is organized by extension
    with tempfile.TemporaryDirectory() as d:
        mk(d,"data.tmp"); mk(d,"x.part")
        r = run(side, d, "--once")
        return r.returncode==0 and (Path(d)/"tmp/data.tmp").is_file() and (Path(d)/"part/x.part").is_file()

PROBES = {k:v for k,v in globals().items() if k.startswith("p_")}
if __name__=="__main__":
    res={}
    for side in ("A","B"):
        res[side]={}
        for k,f in PROBES.items():
            try: res[side][k]="pass" if f(side) else "fail"
            except Exception as e: res[side][k]="fail"; print(side,k,repr(e))
    json.dump(res, open(HERE/"probes/results.json","w"), indent=1)
    print(json.dumps(res, indent=1))
