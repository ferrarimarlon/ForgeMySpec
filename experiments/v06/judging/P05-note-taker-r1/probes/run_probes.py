import json, os, subprocess, sys, tempfile, shutil, glob, stat
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def mk_editor(d, content):
    p = os.path.join(d, "ed.sh")
    with open(p, "w") as f:
        f.write("#!/bin/sh\nprintf '%s' " + repr(content).replace("\\n","\n") + " >> \"$1\"\n" if False else
                "#!/bin/sh\necho 'EDITED_LINE' >> \"$1\"\n")
    os.chmod(p, 0o755); return p
def run(side, home, args, stdin="", env_extra=None):
    env = {"PATH": os.environ["PATH"], "HOME": home, "EDITOR": os.path.join(home, "ed.sh"), "VISUAL": os.path.join(home, "ed.sh")}
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, os.path.join(ROOT, side, "note_taker.py")] + args,
                       input=stdin, capture_output=True, text=True, env=env, timeout=20)
    return r
def ndir(home): return os.path.join(home, ".note-taker")
def files(home): return sorted(glob.glob(os.path.join(ndir(home), "*.md")))
def ids(home): return [os.path.basename(f)[:-3] for f in files(home)]

def probe(side, fn):
    home = tempfile.mkdtemp()
    mk_editor(home, "")
    try:
        return "pass" if fn(side, home) else "fail"
    except Exception as e:
        print(side, fn.__name__, "EXC", repr(e), file=sys.stderr); return "fail"
    finally:
        shutil.rmtree(home)

def p01_new_creates_md_in_home(s, h):
    r = run(s, h, ["new", "Hello World", "-t", "work", "-b", "body text"])
    return r.returncode == 0 and len(files(h)) == 1
def p02_yaml_frontmatter(s, h):
    run(s, h, ["new", "Hello World", "-t", "work", "-t", "ideas", "-b", "body text"])
    t = open(files(h)[0]).read()
    lines = t.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]: return False
    fm = lines[1:lines.index("---", 1)]
    keys = {l.split(":")[0] for l in fm}
    return "title" in keys and "tags" in keys and "work" in t and "ideas" in t and "body text" in t
def p03_list_shows_notes(s, h):
    run(s, h, ["new", "Alpha", "-b", "a"]); run(s, h, ["new", "Beta", "-b", "b"])
    r = run(s, h, ["list"])
    return r.returncode == 0 and "Alpha" in r.stdout and "Beta" in r.stdout
def p04_show(s, h):
    run(s, h, ["new", "Alpha", "-t", "x", "-b", "the secret body"])
    r = run(s, h, ["show", ids(h)[0]])
    return r.returncode == 0 and "the secret body" in r.stdout and "Alpha" in r.stdout
def p05_edit_via_editor(s, h):
    run(s, h, ["new", "Alpha", "-b", "orig"])
    i = ids(h)[0]
    r = run(s, h, ["edit", i])
    t = open(files(h)[0]).read()
    return r.returncode == 0 and "EDITED_LINE" in t and "orig" in t and t.startswith("---")
def p06_delete(s, h):
    run(s, h, ["new", "Alpha", "-b", "a"]); run(s, h, ["new", "Beta", "-b", "b"])
    i = [x for x in ids(h) if "alpha" in x][0]
    r = run(s, h, ["delete", i, "--yes"])
    if r.returncode != 0 and "unrecognized" in r.stderr:
        r = run(s, h, ["delete", i])
    return r.returncode == 0 and len(files(h)) == 1 and "alpha" not in ids(h)[0]
def p07_tag_filter(s, h):
    run(s, h, ["new", "Alpha", "-t", "work", "-b", "a"]); run(s, h, ["new", "Beta", "-t", "home", "-b", "b"])
    r = run(s, h, ["list", "--tag", "work"])
    return r.returncode == 0 and "Alpha" in r.stdout and "Beta" not in r.stdout
def p08_keyword_search_body(s, h):
    run(s, h, ["new", "Alpha", "-b", "contains zebra word"]); run(s, h, ["new", "Beta", "-b", "nothing"])
    r = run(s, h, ["list", "--search", "ZEBRA"])
    return r.returncode == 0 and "Alpha" in r.stdout and "Beta" not in r.stdout
def p09_keyword_search_title(s, h):
    run(s, h, ["new", "Giraffe facts", "-b", "x"]); run(s, h, ["new", "Beta", "-b", "y"])
    r = run(s, h, ["list", "--search", "giraffe"])
    return "Giraffe" in r.stdout and "Beta" not in r.stdout
def p10_show_missing_clean_error(s, h):
    run(s, h, ["new", "Alpha", "-b", "a"])
    r = run(s, h, ["show", "doesnotexist"])
    return r.returncode != 0 and "Traceback" not in r.stderr
def p11_delete_missing_clean_error(s, h):
    r = run(s, h, ["delete", "nope", "--yes"])
    if "unrecognized" in r.stderr: r = run(s, h, ["delete", "nope"])
    return r.returncode != 0 and "Traceback" not in r.stderr
def p12_path_traversal_rejected(s, h):
    os.makedirs(ndir(h), exist_ok=True)
    outside = os.path.join(h, "victim.md"); open(outside, "w").write("---\ntitle: v\n---\nv")
    r = run(s, h, ["delete", "../victim", "--yes"])
    if "unrecognized" in r.stderr: r = run(s, h, ["delete", "../victim"])
    return os.path.exists(outside) and "Traceback" not in r.stderr
def p13_duplicate_title_no_overwrite(s, h):
    run(s, h, ["new", "Same", "-b", "one"]); run(s, h, ["new", "Same", "-b", "two"])
    return len(files(h)) == 2
def p14_title_roundtrip_special(s, h):
    title = 'He said: "hi" #tag, [x]'
    run(s, h, ["new", title, "-b", "b"])
    r = run(s, h, ["show", ids(h)[0]])
    return title in r.stdout
def p15_title_newline_no_corruption(s, h):
    run(s, h, ["new", "line1\nline2", "-t", "keep", "-b", "b"])
    r = run(s, h, ["list", "--tag", "keep"])
    return r.returncode == 0 and "line1" in r.stdout
def p16_stdin_body(s, h):
    run(s, h, ["new", "Piped"], stdin="from stdin body\n")
    t = open(files(h)[0]).read()
    return "from stdin body" in t
def p17_tag_case_insensitive_and_multi_tag(s, h):
    run(s, h, ["new", "Alpha", "-t", "Work,Urgent", "-b", "a"])
    r = run(s, h, ["list", "--tag", "urgent"])
    return "Alpha" in r.stdout
def p18_list_with_bad_file_no_crash(s, h):
    run(s, h, ["new", "Alpha", "-b", "a"])
    open(os.path.join(ndir(h), "bad.md"), "wb").write(b"\xff\xfe\x00garbage")
    r = run(s, h, ["list"])
    return r.returncode == 0 and "Alpha" in r.stdout and "Traceback" not in r.stderr
def p19_handwritten_yaml_block_tags(s, h):
    os.makedirs(ndir(h), exist_ok=True)
    open(os.path.join(ndir(h), "hand.md"), "w").write("---\ntitle: Hand\ntags:\n  - alpha\n  - beta\n---\nhello\n")
    r = run(s, h, ["list", "--tag", "beta"])
    return "Hand" in r.stdout
def p20_stdlib_single_file(s, h):
    src = open(os.path.join(ROOT, s, "note_taker.py")).read()
    import ast
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
    STD={'argparse','datetime','json','os','re','shlex','subprocess','sys','tempfile','pathlib','__future__'}
    return mods <= STD
def p21_edit_missing_clean_error(s, h):
    r = run(s, h, ["edit", "nope"])
    return r.returncode != 0 and "Traceback" not in r.stderr
def p22_edit_updates_timestamp_preserves_tags(s, h):
    run(s, h, ["new", "Alpha", "-t", "keepme", "-b", "a"])
    run(s, h, ["edit", ids(h)[0]])
    r = run(s, h, ["list", "--tag", "keepme"])
    return "Alpha" in r.stdout

PROBES = [v for k, v in sorted(globals().items()) if k.startswith("p") and k[1:3].isdigit()]
res = {}
for side in ("A", "B"):
    res[side] = {f.__name__: probe(side, f) for f in PROBES}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for f in PROBES: print(f.__name__, res["A"][f.__name__], res["B"][f.__name__])
