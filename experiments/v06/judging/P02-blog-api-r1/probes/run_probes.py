"""Black-box probes. Usage: python3 run_probes.py <side_dir> <label>"""
import json, os, subprocess, sys, tempfile, time, http.client, socket, ast

side, label = os.path.abspath(sys.argv[1]), sys.argv[2]
KEY = "probe-key"
tmp = tempfile.mkdtemp()
env = dict(os.environ, BLOG_API_KEY=KEY, BLOG_DB=os.path.join(tmp, "p.db"))
proc = subprocess.Popen([sys.executable, "-I", os.path.join(side, "blog_api.py")], cwd=tmp, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
for _ in range(50):
    try:
        socket.create_connection(("localhost", 8080), 0.2).close(); break
    except OSError:
        time.sleep(0.1)
res, detail = {}, {}

def call(method, path, body=None, key=KEY, raw=None, headers=None):
    c = http.client.HTTPConnection("localhost", 8080, timeout=5)
    h = dict(headers or {})
    if key is not None: h["X-API-Key"] = key
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None: h["Content-Type"] = "application/json"
    try:
        c.request(method, path, body=data, headers=h)
        r = c.getresponse(); b = r.read()
        try: j = json.loads(b) if b else None
        except ValueError: j = "NONJSON"
        return r.status, r.getheader("Content-Type"), j
    except Exception as e:
        return None, None, repr(e)

def probe(pid, fn):
    try:
        ok, d = fn()
    except Exception as e:
        ok, d = False, repr(e)
    res[pid] = "pass" if ok else "fail"; detail[pid] = d

src = open(os.path.join(side, "blog_api.py")).read()
tree = ast.parse(src)
mods = {n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
       {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
probe("P01_stdlib_only", lambda: (mods <= {"hmac","json","os","re","sqlite3","http","secrets","threading","datetime","urllib","sys","time","uuid","typing","collections","functools","hashlib","logging","argparse","signal","socket","contextlib","dataclasses"}, sorted(mods)))
probe("P02_uses_http_server_sqlite3", lambda: ({"http", "sqlite3"} <= mods, sorted(mods)))
probe("P03_single_file", lambda: (os.path.isfile(os.path.join(side, "blog_api.py")), "ok"))
probe("P04_listens_8080", lambda: (call("GET", "/posts")[0] is not None, "conn"))

s, ct, j = call("POST", "/posts", {"title": "Hello", "content": "World"})
pid = j.get("id") if isinstance(j, dict) else None
probe("P05_create_201_returns_post", lambda: (s in (200, 201) and isinstance(j, dict) and j.get("title") == "Hello" and pid is not None, [s, j]))
probe("P06_json_content_type", lambda: (ct is not None and ct.startswith("application/json"), ct))
def p7():
    s, _, j = call("GET", "/posts"); return s == 200 and isinstance(j, list) and any(p.get("id") == pid for p in j), [s, j]
probe("P07_list_posts", p7)
def p8():
    s, _, j = call("GET", f"/posts/{pid}"); return s == 200 and j.get("content") == "World", [s, j]
probe("P08_get_one", p8)
probe("P09_get_missing_404", lambda: (call("GET", "/posts/999999")[0] == 404, call("GET", "/posts/999999")))
def p10():
    s, _, j = call("PUT", f"/posts/{pid}", {"title": "New", "content": "Body"})
    s2, _, j2 = call("GET", f"/posts/{pid}")
    return s == 200 and j2.get("title") == "New" and j2.get("content") == "Body", [s, j, j2]
probe("P10_update_put", p10)
probe("P11_update_missing_404", lambda: (call("PUT", "/posts/999999", {"title": "x", "content": "y"})[0] == 404, call("PUT", "/posts/999999", {"title": "x", "content": "y"})))
probe("P12_no_key_401", lambda: (call("GET", "/posts", key=None)[0] in (401, 403), call("GET", "/posts", key=None)))
probe("P13_wrong_key_401", lambda: (call("GET", "/posts", key="wrong")[0] in (401, 403), call("GET", "/posts", key="wrong")))
def p14():
    s, _, _ = call("POST", "/posts", {"title": "x", "content": "y"}, key="wrong")
    _, _, lst = call("GET", "/posts"); return s in (401, 403) and not any(p.get("title") == "x" for p in lst), s
probe("P14_unauth_write_blocked", p14)
probe("P15_invalid_json_400", lambda: (call("POST", "/posts", raw=b"{bad")[0] == 400, call("POST", "/posts", raw=b"{bad")))
probe("P16_missing_title_400", lambda: (call("POST", "/posts", {"content": "c"})[0] == 400, call("POST", "/posts", {"content": "c"})))
probe("P17_wrong_type_400", lambda: (call("POST", "/posts", {"title": 5, "content": "c"})[0] == 400, call("POST", "/posts", {"title": 5, "content": "c"})))
probe("P18_non_object_400", lambda: (call("POST", "/posts", [1, 2])[0] == 400, call("POST", "/posts", [1, 2])))
probe("P19_empty_body_400", lambda: (call("POST", "/posts", raw=b"")[0] == 400, call("POST", "/posts", raw=b"")))
probe("P20_unknown_route_404", lambda: (call("GET", "/nope")[0] == 404 and isinstance(call("GET", "/nope")[2], dict), call("GET", "/nope")))
def p21():
    r = call("POST", "/posts", raw=b'{"title":"a","content":"\\ud800"}')
    alive = call("GET", "/posts")[0] == 200
    return r[0] is not None and r[0] < 600 and isinstance(r[2], dict) and alive, [r, alive]
probe("P21_lone_surrogate_gets_json_response", p21)
probe("P22_sqli_id_path", lambda: (call("GET", "/posts/1%20OR%201=1")[0] in (400, 404), call("GET", "/posts/1%20OR%201=1")))
def p23():
    s, _, _ = call("DELETE", f"/posts/{pid}")
    s2 = call("GET", f"/posts/{pid}")[0]; s3 = call("DELETE", f"/posts/{pid}")[0]
    return s in (200, 204) and s2 == 404 and s3 == 404, [s, s2, s3]
probe("P23_delete_then_404", p23)
def p24():
    _, _, a = call("POST", "/posts", {"title": "persist", "content": "c"})
    proc.terminate(); proc.wait(5)
    p2 = subprocess.Popen([sys.executable, "-I", os.path.join(side, "blog_api.py")], cwd=tmp, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try: socket.create_connection(("localhost", 8080), 0.2).close(); break
        except OSError: time.sleep(0.1)
    s, _, j = call("GET", f"/posts/{a['id']}")
    p2.terminate(); p2.wait(5)
    return s == 200 and j.get("title") == "persist", [s, j]
probe("P24_persists_across_restart", p24)
print(json.dumps({"label": label, "results": res, "detail": detail}, default=str))
