"""Black-box probes. Usage: python3 probes/run_probes.py  (runs on A and B)"""
import ast, json, os, subprocess, sys, tempfile, shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {
    "argparse","datetime","os","re","shlex","subprocess","sys","tempfile","pathlib","json","shutil","textwrap","time","glob","io","string","uuid","fnmatch","collections","typing","dataclasses","contextlib","functools","itertools","unicodedata","hashlib","errno","stat","locale","getpass","signal","platform","enum"}

# Only the invocation differs per side.
DELETE_EXTRA = {"A": ["-y"], "B": []}

def mk_env(home):
    env = {k: v for k, v in os.environ.items() if k not in ("VISUAL", "EDITOR", "NOTE_TAKER_DIR")}
    env["HOME"] = str(home)
    return env

def run(side, home, *args, env_extra=None, stdin=""):
    env = mk_env(home)
    if env_extra: env.update(env_extra)
    return subprocess.run([sys.executable, str(ROOT/side/"note_taker.py"), *args], input=stdin,
                          capture_output=True, text=True, env=env, timeout=30)

def nid(r): return r.stdout.strip().split()[-1]

def ndir(home): return Path(home)/".note-taker"

def fm(path):
    t = path.read_text()
    assert t.startswith("---\n")
    end = t.index("\n---", 4)
    return yaml.safe_load(t[4:end])

def editor_script(tmp, body):
    p = Path(tmp)/"ed.sh"
    p.write_text(body); p.chmod(0o755); return str(p)

def probes(side):
    res = {}
    def probe(name):
        def deco(f):
            tmp = tempfile.mkdtemp(); home = Path(tmp)/"home"; home.mkdir()
            try:
                ok = f(home, tmp)
                res[name] = "pass" if ok else "fail"
            except Exception as e:
                res[name] = "fail"; print(side, name, "EXC", repr(e))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        return deco

    @probe("P01_new_creates_md_in_home_dir")
    def _(h, t):
        r = run(side, h, "new", "Hello World", "--tags", "a,b", "--body", "hi there")
        files = list(ndir(h).glob("*.md"))
        return r.returncode == 0 and len(files) == 1 and nid(r) == files[0].stem

    @probe("P02_frontmatter_valid_yaml_title_tags")
    def _(h, t):
        run(side, h, "new", "Hello World", "--tags", "a,b", "--body", "hi there")
        d = fm(next(ndir(h).glob("*.md")))
        return d["title"] == "Hello World" and list(d["tags"]) == ["a", "b"] and "hi there" in next(ndir(h).glob("*.md")).read_text()

    @probe("P03_list_shows_notes")
    def _(h, t):
        run(side, h, "new", "Alpha", "--body", "x"); run(side, h, "new", "Beta", "--body", "y")
        r = run(side, h, "list")
        return r.returncode == 0 and "Alpha" in r.stdout and "Beta" in r.stdout

    @probe("P04_show_prints_title_and_body")
    def _(h, t):
        i = nid(run(side, h, "new", "Alpha", "--body", "secret body text"))
        r = run(side, h, "show", i)
        return r.returncode == 0 and "Alpha" in r.stdout and "secret body text" in r.stdout

    @probe("P05_edit_via_editor_persists")
    def _(h, t):
        i = nid(run(side, h, "new", "Alpha", "--body", "orig"))
        ed = editor_script(t, '#!/bin/sh\necho "EDITED LINE" >> "$1"\n')
        r = run(side, h, "edit", i, env_extra={"EDITOR": ed})
        s = run(side, h, "show", i)
        return r.returncode == 0 and "EDITED LINE" in s.stdout and "orig" in s.stdout

    @probe("P06_delete_removes_file")
    def _(h, t):
        i = nid(run(side, h, "new", "Alpha", "--body", "x"))
        r = run(side, h, "delete", i, *DELETE_EXTRA[side])
        return r.returncode == 0 and not list(ndir(h).glob("*.md"))

    @probe("P07_list_filter_by_tag")
    def _(h, t):
        run(side, h, "new", "Alpha", "--tags", "work", "--body", "x")
        run(side, h, "new", "Beta", "--tags", "home", "--body", "y")
        r = run(side, h, "list", "--tag", "work")
        return r.returncode == 0 and "Alpha" in r.stdout and "Beta" not in r.stdout

    @probe("P08_list_search_keyword_body")
    def _(h, t):
        run(side, h, "new", "Alpha", "--body", "contains zebra")
        run(side, h, "new", "Beta", "--body", "nothing")
        r = run(side, h, "list", "--search", "ZEBRA")
        return r.returncode == 0 and "Alpha" in r.stdout and "Beta" not in r.stdout

    @probe("P09_list_search_keyword_title")
    def _(h, t):
        run(side, h, "new", "Giraffe facts", "--body", "a")
        run(side, h, "new", "Beta", "--body", "b")
        r = run(side, h, "list", "--search", "giraffe")
        return r.returncode == 0 and "Giraffe" in r.stdout and "Beta" not in r.stdout

    @probe("P10_show_missing_clean_error")
    def _(h, t):
        r = run(side, h, "show", "nope")
        return r.returncode != 0 and "Traceback" not in r.stderr

    @probe("P11_delete_missing_clean_error")
    def _(h, t):
        r = run(side, h, "delete", "nope", *DELETE_EXTRA[side])
        return r.returncode != 0 and "Traceback" not in r.stderr

    @probe("P12_duplicate_titles_distinct_files")
    def _(h, t):
        a = nid(run(side, h, "new", "Same", "--body", "one"))
        b = nid(run(side, h, "new", "Same", "--body", "two"))
        return a != b and len(list(ndir(h).glob("*.md"))) == 2 and "one" in run(side, h, "show", a).stdout and "two" in run(side, h, "show", b).stdout

    @probe("P13_special_title_yaml_roundtrip")
    def _(h, t):
        title = 'Meeting: "Q3" plan'
        i = nid(run(side, h, "new", title, "--body", "x"))
        d = fm(ndir(h)/f"{i}.md")
        return d["title"] == title and title in run(side, h, "show", i).stdout

    @probe("P14_special_tag_yaml_valid")
    def _(h, t):
        run(side, h, "new", "T", "--tags", "#urgent,c++", "--body", "x")
        d = fm(next(ndir(h).glob("*.md")))
        return [str(x).lower() for x in d["tags"]] == ["#urgent", "c++"]

    @probe("P15_single_file_stdlib_only")
    def _(h, t):
        src = (ROOT/side/"note_taker.py").read_text()
        mods = set()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
        return mods <= STDLIB

    @probe("P16_list_tolerates_malformed_file")
    def _(h, t):
        run(side, h, "new", "Good", "--body", "x")
        (ndir(h)/"bad.md").write_bytes(b"\xff\xfe garbage")
        (ndir(h)/"bad2.md").write_text("---\nno end")
        r = run(side, h, "list")
        return r.returncode == 0 and "Good" in r.stdout and "Traceback" not in r.stderr

    @probe("P17_edit_failing_editor_clean_error")
    def _(h, t):
        i = nid(run(side, h, "new", "Alpha", "--body", "x"))
        r = run(side, h, "edit", i, env_extra={"EDITOR": "false"})
        return r.returncode != 0 and "Traceback" not in r.stderr

    @probe("P18_show_path_traversal_rejected")
    def _(h, t):
        (Path(h)/"outside.md").write_text("---\nid: outside\ntitle: OUTSIDE\ntags: []\ncreated: x\n---\nLEAK\n")
        run(side, h, "new", "Alpha", "--body", "x")
        r = run(side, h, "show", "../outside")
        return "LEAK" not in r.stdout

    @probe("P19_unicode_body_roundtrip")
    def _(h, t):
        i = nid(run(side, h, "new", "Café", "--body", "naïve — 日本"))
        return "naïve — 日本" in run(side, h, "show", i).stdout

    @probe("P20_frontmatter_valid_after_edit")
    def _(h, t):
        i = nid(run(side, h, "new", "Alpha", "--tags", "x", "--body", "orig"))
        ed = editor_script(t, '#!/bin/sh\necho "more" >> "$1"\n')
        run(side, h, "edit", i, env_extra={"EDITOR": ed})
        d = fm(ndir(h)/f"{i}.md")
        return d["title"] == "Alpha" and list(d["tags"]) == ["x"]

    @probe("P21_body_from_stdin")
    def _(h, t):
        r = run(side, h, "new", "Piped", stdin="piped body text\n")
        i = nid(r)
        return "piped body text" in run(side, h, "show", i).stdout

    @probe("P22_yaml_title_scalar_types_preserved")
    def _(h, t):
        i = nid(run(side, h, "new", "- todo", "--body", "x"))
        j = nid(run(side, h, "new", "123", "--body", "x"))
        return fm(ndir(h)/f"{i}.md")["title"] == "- todo" and fm(ndir(h)/f"{j}.md")["title"] == "123"

    @probe("P23_list_empty_store_ok")
    def _(h, t):
        r = run(side, h, "list")
        return r.returncode == 0 and "Traceback" not in r.stderr
    return res

if __name__ == "__main__":
    out = {"A": probes("A"), "B": probes("B")}
    (ROOT/"probes"/"results.json").write_text(json.dumps(out, indent=1))
    for k in out["A"]:
        print(f"{k:45} A={out['A'][k]:5} B={out['B'][k]}")
