import http.client, json, os, subprocess, sys, tempfile, time, shutil, ast
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KEY = "probe-key-123"

def req(method, path, body=None, key=KEY, raw=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", 8080, timeout=5)
    h = dict(headers or {})
    if key is not None: h["X-API-Key"] = key
    data = raw if raw is not None else (json.dumps(body) if body is not None else None)
    if data is not None: h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse(); t = r.read(); c.close()
    try: j = json.loads(t) if t else None
    except Exception: j = "NOTJSON"
    return r.status, j, r.getheader("Content-Type")

def start(side, tmp):
    env = dict(os.environ, BLOG_API_KEY=KEY, BLOG_DB=os.path.join(tmp, "a.db"), BLOG_DB_PATH=os.path.join(tmp, "a.db"))
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, side, "blog_api.py")], cwd=tmp, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(50):
        try:
            http.client.HTTPConnection("127.0.0.1", 8080, timeout=1).connect(); return p
        except OSError: time.sleep(0.1)
    return p

def run(side):
    res = {}
    def chk(pid, fn):
        try: res[pid] = "pass" if fn() else "fail"
        except Exception as e: res[pid] = "fail"; print(side, pid, "EXC", repr(e))
    src = open(os.path.join(ROOT, side, "blog_api.py")).read()
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom): mods.add(n.module.split(".")[0])
    chk("P01_stdlib_only", lambda: mods <= {"hmac","json","os","re","sqlite3","threading","datetime","http","sys","traceback","urllib","time","uuid","hashlib","secrets","argparse","logging","contextlib","typing"})
    chk("P02_single_file", lambda: os.path.isfile(os.path.join(ROOT, side, "blog_api.py")))
    tmp = tempfile.mkdtemp()
    p = start(side, tmp)
    try:
        chk("P03_listens_8080", lambda: req("GET", "/posts")[0] == 200)
        st = {}
        def create():
            s, j, ct = req("POST", "/posts", {"title": "T1", "content": "C1"})
            st["id"] = j["id"]; return s == 201 and j["title"] == "T1" and j["content"] == "C1"
        chk("P04_create_201", create)
        chk("P05_get_one", lambda: (lambda r: r[0] == 200 and r[1]["title"] == "T1")(req("GET", f"/posts/{st['id']}")))
        chk("P06_list_contains", lambda: (lambda r: r[0] == 200 and any(x["id"] == st["id"] for x in r[1]))(req("GET", "/posts")))
        chk("P07_update_put", lambda: (lambda r: r[0] == 200 and r[1]["title"] == "T2")(req("PUT", f"/posts/{st['id']}", {"title": "T2", "content": "C2"})))
        chk("P08_update_persisted", lambda: req("GET", f"/posts/{st['id']}")[1]["content"] == "C2")
        chk("P09_post_no_key_401", lambda: req("POST", "/posts", {"title": "x", "content": "y"}, key=None)[0] in (401, 403))
        chk("P10_post_bad_key_401", lambda: req("POST", "/posts", {"title": "x", "content": "y"}, key="wrong")[0] in (401, 403))
        chk("P11_put_no_key_401", lambda: req("PUT", f"/posts/{st['id']}", {"title": "x", "content": "y"}, key=None)[0] in (401, 403))
        chk("P12_delete_no_key_401", lambda: req("DELETE", f"/posts/{st['id']}", key=None)[0] in (401, 403))
        chk("P13_invalid_json_400", lambda: req("POST", "/posts", raw="{bad")[0] == 400)
        chk("P14_missing_title_400", lambda: req("POST", "/posts", {"content": "y"})[0] == 400)
        chk("P15_non_object_400", lambda: req("POST", "/posts", [1, 2])[0] == 400)
        chk("P16_wrong_type_400", lambda: req("POST", "/posts", {"title": 5, "content": "y"})[0] == 400)
        chk("P17_json_content_type", lambda: "application/json" in (req("GET", "/posts")[2] or ""))
        chk("P18_get_missing_404", lambda: req("GET", "/posts/99999")[0] == 404)
        chk("P19_unknown_route_404", lambda: req("GET", "/nope")[0] == 404)
        chk("P20_get_id0_404", lambda: req("GET", "/posts/0")[0] == 404)
        chk("P21_put_missing_404", lambda: req("PUT", "/posts/99999", {"title": "a", "content": "b"})[0] == 404)
        chk("P22_delete_ok", lambda: req("DELETE", f"/posts/{st['id']}")[0] in (200, 204))
        chk("P23_deleted_gone_404", lambda: req("GET", f"/posts/{st['id']}")[0] == 404)
        chk("P24_delete_missing_404", lambda: req("DELETE", "/posts/99999")[0] == 404)
        chk("P25_error_body_json", lambda: isinstance(req("GET", "/posts/99999")[1], dict))
        chk("P26_sqli_title_stored_literally", lambda: (lambda r: req("GET", f"/posts/{r[1]['id']}")[1]["title"] == "x'); DROP TABLE posts;--")(req("POST", "/posts", {"title": "x'); DROP TABLE posts;--", "content": "c"})))
        def many():
            for i in range(60): req("POST", "/posts", {"title": f"m{i}", "content": "c"})
            return len(req("GET", "/posts")[1]) >= 61
        chk("P27_list_returns_all_posts", many)
        chk("P28_persist_after_restart", lambda: True)
        p.terminate(); p.wait(5)
        p = start(side, tmp)
        res["P28_persist_after_restart"] = "pass" if any(x["title"] == "m0" for x in req("GET", "/posts")[1]) else "fail"
    finally:
        p.terminate(); p.wait(5); shutil.rmtree(tmp)
    return res

out = {s: run(s) for s in ("A", "B")}
json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1)
for s in out:
    print(s, sum(v == "pass" for v in out[s].values()), "/", len(out[s]), [k for k, v in out[s].items() if v == "fail"])
