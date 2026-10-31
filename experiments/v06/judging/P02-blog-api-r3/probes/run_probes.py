"""Black-box probes. Usage: python3 -I run_probes.py <side_dir> <side_name> <results.json>
Both sides launched identically: cwd=tempdir, env BLOG_API_KEY=k123, python3 <side>/blog_api.py.
Payloads include both 'body' and 'content' so either field naming is accepted (invocation adaptation only)."""
import json, os, subprocess, sys, tempfile, time, socket, http.client, ast

side_dir, side, out = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
KEY = "k123"
R = {}

def req(method, path, body=None, key=KEY, raw=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", 8080, timeout=5)
    h = dict(headers or {})
    if key is not None: h["X-API-Key"] = key
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None: h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse(); b = r.read(); ct = r.getheader("Content-Type", "")
    c.close()
    try: j = json.loads(b) if b else None
    except Exception: j = "NONJSON"
    return r.status, ct, j

def wait_up(proc):
    for _ in range(50):
        if proc.poll() is not None: return False
        try: socket.create_connection(("127.0.0.1", 8080), 0.2).close(); return True
        except OSError: time.sleep(0.1)
    return False

def start(tmp, env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("BLOG")}
    env.update(env_extra)
    p = subprocess.Popen([sys.executable, os.path.join(side_dir, "blog_api.py")], cwd=tmp, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p

def stop(p):
    p.terminate()
    try: p.wait(5)
    except Exception: p.kill()

def rec(pid, cond): R[pid] = "pass" if cond else "fail"

# P01 single file + stdlib-only imports
src = open(os.path.join(side_dir, "blog_api.py")).read()
mods = set()
for n in ast.walk(ast.parse(src)):
    if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
    if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
rec("P01_stdlib_only", mods <= set(sys.stdlib_module_names))
rec("P02_single_file_blog_api_py", os.path.isfile(os.path.join(side_dir, "blog_api.py")))

tmp = tempfile.mkdtemp()
p = start(tmp, {"BLOG_API_KEY": KEY})
up = wait_up(p)
rec("P03_listens_8080", up)
if up:
    P = {"title": "Hello", "body": "World", "content": "World"}
    s, ct, j = req("POST", "/posts", P)
    rec("P04_create_201", s == 201 and isinstance(j, dict) and j.get("title") == "Hello" and isinstance(j.get("id"), int))
    pid = j.get("id") if isinstance(j, dict) else 1
    rec("P05_json_content_type", "application/json" in ct)
    s, _, j = req("GET", f"/posts/{pid}")
    rec("P06_get_one", s == 200 and isinstance(j, dict) and j.get("id") == pid and j.get("title") == "Hello")
    s, _, j = req("GET", "/posts")
    rec("P07_list", s == 200 and isinstance(j, list) and any(x.get("id") == pid for x in j))
    s, ct, j = req("GET", "/posts/99999")
    rec("P08_get_missing_404", s == 404 and isinstance(j, dict))
    s, _, j = req("PUT", f"/posts/{pid}", {"title": "New", "body": "B2", "content": "B2"})
    s2, _, j2 = req("GET", f"/posts/{pid}")
    rec("P09_update", s == 200 and isinstance(j2, dict) and j2.get("title") == "New")
    s, _, _ = req("PUT", "/posts/99999", {"title": "x", "body": "y", "content": "y"})
    rec("P10_update_missing_404", s == 404)
    s, _, _ = req("GET", "/posts", key=None)
    rec("P11_no_key_401_403", s in (401, 403))
    s, _, _ = req("GET", "/posts", key="wrong")
    rec("P12_bad_key_401_403", s in (401, 403))
    s, _, _ = req("POST", "/posts", P, key=None)
    s2, _, j2 = req("GET", "/posts")
    rec("P13_unauth_post_not_created", s in (401, 403) and isinstance(j2, list) and len(j2) == 1)
    s, ct, j = req("POST", "/posts", raw=b"{not json")
    rec("P14_invalid_json_400", s == 400 and isinstance(j, dict))
    s, _, _ = req("POST", "/posts", {"body": "x", "content": "x"})
    rec("P15_missing_title_4xx", s in (400, 422))
    s, _, _ = req("POST", "/posts", [1, 2])
    rec("P16_non_object_4xx", s in (400, 422))
    s, _, _ = req("POST", "/posts", {"title": 5, "body": "x", "content": "x"})
    rec("P17_wrong_type_4xx", s in (400, 422))
    s, ct, j = req("GET", "/nope")
    rec("P18_unknown_route_404_json", s == 404 and "application/json" in ct and isinstance(j, dict))
    s, ct, j = req("GET", "/posts", key="wrong")
    rec("P19_error_body_json", "application/json" in ct and isinstance(j, dict))
    s, _, _ = req("DELETE", f"/posts/{pid}")
    s2, _, _ = req("GET", f"/posts/{pid}")
    rec("P20_delete", s in (200, 204) and s2 == 404)
    s, _, _ = req("DELETE", f"/posts/{pid}")
    rec("P21_delete_missing_404", s == 404)
    # SQL-ish payload stored literally
    s, _, j = req("POST", "/posts", {"title": "x'); DROP TABLE posts;--", "body": "b", "content": "b"})
    s2, _, j2 = req("GET", "/posts")
    rec("P22_sql_injection_literal", s == 201 and isinstance(j2, list) and any(x.get("title") == "x'); DROP TABLE posts;--" for x in j2))
    s, _, _ = req("POST", "/posts", raw=b"\xff\xfe")
    rec("P23_bad_utf8_400", s == 400)
    s, _, _ = req("GET", "/posts")
    rec("P24_alive_after_bad_input", s == 200)
    # persistence across restart
    req("POST", "/posts", {"title": "Persist", "body": "p", "content": "p"})
    stop(p)
    p = start(tmp, {"BLOG_API_KEY": KEY}); wait_up(p)
    s, _, j = req("GET", "/posts")
    rec("P25_persist_sqlite_restart", s == 200 and isinstance(j, list) and any(x.get("title") == "Persist" for x in j))
    rec("P26_db_file_sqlite", any(open(os.path.join(tmp, f), "rb").read(16).startswith(b"SQLite format 3") for f in os.listdir(tmp) if os.path.isfile(os.path.join(tmp, f))))
    # not exposed on non-loopback
    rec("P27_bound_localhost", True)
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if not ip.startswith("127."):
            try: socket.create_connection((ip, 8080), 0.5).close(); R["P27_bound_localhost"] = "fail"
            except OSError: pass
    except Exception: pass
stop(p)
# P28: no API key configured -> server must not accept a guessable default key
tmp2 = tempfile.mkdtemp()
p = start(tmp2, {})
up = wait_up(p)
if up:
    try: s, _, _ = req("GET", "/posts", key="dev-key"); s2, _, _ = req("GET", "/posts", key="")
    except Exception: s = s2 = 0
    rec("P28_no_default_key_when_unset", s in (401, 403) and s2 in (401, 403))
else:
    rec("P28_no_default_key_when_unset", True)  # refused to start: secure
stop(p)
for t in range(50):
    try: socket.create_connection(("127.0.0.1", 8080), 0.2).close(); time.sleep(0.1)
    except OSError: break
all_r = json.load(open(out)) if os.path.exists(out) else {}
all_r[side] = R
json.dump(all_r, open(out, "w"), indent=1)
print(side, json.dumps(R, indent=1))
