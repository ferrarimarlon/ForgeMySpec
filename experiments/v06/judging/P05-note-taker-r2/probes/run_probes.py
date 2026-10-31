"""Black-box probes. Usage: python3 run_probes.py <side_dir>; prints JSON {probe: pass|fail}."""
import ast, json, os, subprocess, sys, tempfile, pathlib, shutil

SIDE = pathlib.Path(sys.argv[1]).resolve()
NAME = SIDE.name
PROG = SIDE / "note_taker.py"
results = {}

def setup():
    home = pathlib.Path(tempfile.mkdtemp())
    ed = home / "ed.sh"
    ed.write_text('#!/bin/sh\nprintf "\\nEDITED-LINE\\n" >> "$1"\n'); ed.chmod(0o755)
    return home, ed

def run(home, args, stdin=b"", ed=None):
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    if ed: env["EDITOR"] = str(ed)
    # interface adaptation only: A's delete asks confirmation (-y)
    if NAME == "A" and args and args[0] == "delete":
        args = ["delete", "-y"] + args[1:]
    p = subprocess.run([sys.executable, str(PROG)] + args, input=stdin, env=env,
                       capture_output=True, timeout=20, cwd=home)
    return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")

def ndir(home): return home / ".note-taker"

def new(home, title, tags=(), body="hello body"):
    before = set(ndir(home).glob("*.md")) if ndir(home).exists() else set()
    a = ["new", title, "--body", body]
    for t in tags: a += ["--tag", t]
    rc, out, err = run(home, a)
    after = set(ndir(home).glob("*.md")) if ndir(home).exists() else set()
    created = list(after - before)
    return rc, (created[0].stem if len(created) == 1 else None)

def probe(pid):
    def deco(f):
        home, ed = setup()
        try: results[pid] = "pass" if f(home, ed) else "fail"
        except Exception as e: results[pid] = "fail"; print(pid, "EXC", repr(e), file=sys.stderr)
        finally: shutil.rmtree(home, ignore_errors=True)
    return deco

@probe("P01_new_creates_md_in_home_dir")
def _(h, ed):
    rc, nid = new(h, "First Note")
    return rc == 0 and nid is not None and (ndir(h) / f"{nid}.md").is_file()

@probe("P02_yaml_frontmatter")
def _(h, ed):
    rc, nid = new(h, "Front", tags=["work"])
    t = (ndir(h) / f"{nid}.md").read_text()
    lines = t.split("\n")
    end = lines.index("---", 1)
    fm = "\n".join(lines[1:end])
    return lines[0] == "---" and "title:" in fm and "Front" in fm and "tags:" in fm and "work" in fm and "hello body" in "\n".join(lines[end+1:])

@probe("P03_list_shows_note")
def _(h, ed):
    new(h, "Listed One"); rc, out, _ = run(h, ["list"])
    return rc == 0 and "Listed One" in out

@probe("P04_show_displays_note")
def _(h, ed):
    _, nid = new(h, "Showable", body="the secret body text")
    rc, out, _ = run(h, ["show", nid])
    return rc == 0 and "Showable" in out and "the secret body text" in out

@probe("P05_edit_persists")
def _(h, ed):
    _, nid = new(h, "Editable")
    rc, out, err = run(h, ["edit", nid], ed=ed)
    t = (ndir(h) / f"{nid}.md").read_text()
    return rc == 0 and "EDITED-LINE" in t and t.startswith("---")

@probe("P06_delete_removes")
def _(h, ed):
    _, nid = new(h, "Doomed")
    rc, _, _ = run(h, ["delete", nid])
    return rc == 0 and not (ndir(h) / f"{nid}.md").exists()

@probe("P07_filter_by_tag")
def _(h, ed):
    new(h, "Alpha note", tags=["work"]); new(h, "Beta note", tags=["home"])
    rc, out, _ = run(h, ["list", "--tag", "work"])
    return rc == 0 and "Alpha note" in out and "Beta note" not in out

@probe("P08_keyword_in_body")
def _(h, ed):
    new(h, "Gamma", body="contains zebra word"); new(h, "Delta", body="nothing")
    rc, out, _ = run(h, ["list", "--search", "zebra"])
    return rc == 0 and "Gamma" in out and "Delta" not in out

@probe("P09_keyword_in_title")
def _(h, ed):
    new(h, "Quarterly Report"); new(h, "Groceries")
    rc, out, _ = run(h, ["list", "--search", "quarterly"])
    return rc == 0 and "Quarterly Report" in out and "Groceries" not in out

@probe("P10_show_missing_graceful")
def _(h, ed):
    new(h, "Something")
    rc, out, err = run(h, ["show", "does-not-exist"])
    return rc != 0 and "Traceback" not in err

@probe("P11_delete_missing_graceful")
def _(h, ed):
    new(h, "Something")
    rc, out, err = run(h, ["delete", "does-not-exist"])
    return rc != 0 and "Traceback" not in err and len(list(ndir(h).glob("*.md"))) == 1

@probe("P12_edit_missing_graceful")
def _(h, ed):
    new(h, "Something")
    rc, out, err = run(h, ["edit", "does-not-exist"], ed=ed)
    return rc != 0 and "Traceback" not in err

@probe("P13_yaml_special_chars_title_roundtrip")
def _(h, ed):
    title = 'Meeting: "Q3" #plan [draft]'
    _, nid = new(h, title)
    rc, out, _ = run(h, ["list"])
    return rc == 0 and title in out

@probe("P14_newline_in_title_no_corruption")
def _(h, ed):
    _, nid = new(h, "line1\nline2: x")
    new(h, "Other")
    rc, out, _ = run(h, ["list"])
    rc2, out2, err2 = run(h, ["show", nid])
    return rc == 0 and "line1\nline2: x" in out and rc2 == 0 and "Traceback" not in err2

@probe("P15_duplicate_titles_distinct")
def _(h, ed):
    _, a = new(h, "Same", body="one"); _, b = new(h, "Same", body="two")
    return a and b and a != b and len(list(ndir(h).glob("*.md"))) == 2

@probe("P16_no_path_traversal_delete")
def _(h, ed):
    new(h, "Inside")
    victim = h / "victim.md"; victim.write_text("---\ntitle: v\n---\nkeep\n")
    run(h, ["delete", "../victim"])
    return victim.exists()

@probe("P17_no_path_traversal_show")
def _(h, ed):
    new(h, "Inside")
    victim = h / "secret.md"; victim.write_text("---\ntitle: s\n---\nTOPSECRET\n")
    rc, out, _ = run(h, ["show", "../secret"])
    return "TOPSECRET" not in out

@probe("P18_tag_with_space_or_quote_roundtrip")
def _(h, ed):
    new(h, "Tagged", tags=['to "do"'])
    rc, out, _ = run(h, ["list", "--tag", 'to "do"'])
    return rc == 0 and "Tagged" in out

@probe("P19_handwritten_note_listed")
def _(h, ed):
    new(h, "Seed")
    (ndir(h) / "manual.md").write_text("---\ntitle: Manual Note\ntags: [x, y]\n---\n\nbody kiwi\n")
    rc, out, _ = run(h, ["list", "--tag", "y"]); rc2, out2, _ = run(h, ["list", "--search", "kiwi"])
    return "Manual Note" in out and "Manual Note" in out2

@probe("P20_single_file_stdlib_only")
def _(h, ed):
    files = [p for p in SIDE.rglob("*.py")]
    tree = ast.parse(PROG.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    import importlib.util, sysconfig
    std = sysconfig.get_paths()["stdlib"]
    def is_std(m):
        if m in sys.builtin_module_names: return True
        sp = importlib.util.find_spec(m)
        return sp is not None and sp.origin is not None and (sp.origin.startswith(std) and "site-packages" not in sp.origin or sp.origin in ("built-in", "frozen"))
    return len(files) == 1 and all(is_std(m) for m in mods)

@probe("P21_empty_list_ok")
def _(h, ed):
    rc, out, err = run(h, ["list"])
    return rc == 0 and "Traceback" not in err

print(json.dumps(results))
