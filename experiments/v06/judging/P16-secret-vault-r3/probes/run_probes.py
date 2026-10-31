import json, os, subprocess, sys, tempfile, stat, re, shutil
from datetime import datetime, timezone, timedelta
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "correct-horse"
def mk(side):
    home = tempfile.mkdtemp()
    def run(*args, pw=PW, stdin=None):
        import site; env = {"HOME": home, "PATH": os.environ["PATH"], "PYTHONUSERBASE": site.getuserbase()}
        if pw is not None: env["VAULT_MASTER_KEY"] = pw
        r = subprocess.run([sys.executable, os.path.join(ROOT, side, "vault.py"), *args],
                           env=env, capture_output=True, text=True, input=stdin or "", timeout=60)
        return r
    return home, run
def decrypt(home, pw=PW):
    import base64
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    blob = open(os.path.join(home, ".vault", "vault.enc"), "rb").read()
    for off in range(0, 9):
        salt = blob[off:off+16]; tok = blob[off+16:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000)
        try:
            return json.loads(Fernet(base64.urlsafe_b64encode(kdf.derive(pw.encode()))).decrypt(tok)), off
        except Exception:
            continue
    return None, None
def find_exp(d, key):
    e = d[key]
    if isinstance(e, dict):
        for k, v in e.items():
            if "exp" in k: return v
    return None
def set_expiry_past(home, key):
    import base64
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    p = os.path.join(home, ".vault", "vault.enc")
    blob = open(p, "rb").read()
    d, off = decrypt(home)
    for k in d[key]:
        if "exp" in k: d[key][k] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    salt = blob[off:off+16]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000)
    tok = Fernet(base64.urlsafe_b64encode(kdf.derive(PW.encode()))).encrypt(json.dumps(d).encode())
    open(p, "wb").write(blob[:off+16] + tok)

def probes(side):
    res = {}
    def P(name, fn):
        try: res[name] = "pass" if fn() else "fail"
        except Exception as e: res[name] = "fail"; print(side, name, "EXC", e)
    def p01():  # set/get roundtrip, get prints only value
        h, r = mk(side)
        a = r("set", "db_pass", "s3cretvalue"); b = r("get", "db_pass")
        return a.returncode == 0 and b.returncode == 0 and b.stdout.strip() == "s3cretvalue" and b.stdout.strip("\n") == "s3cretvalue"
    def p02():  # env var used; wrong pw fails 2
        h, r = mk(side); r("set", "k", "value1")
        return r("get", "k", pw="wrong").returncode == 2
    def p03():  # no --password style CLI arg
        h, r = mk(side)
        a = r("--password", PW, "list", pw=None); b = r("list", "--master-key", PW, pw=None)
        return a.returncode != 0 and b.returncode != 0
    def p04():  # missing env -> nonzero, no traceback
        h, r = mk(side); r("set", "k", "value1")
        x = r("get", "k", pw=None)
        return x.returncode in (1, 2) and "Traceback" not in x.stderr and "value1" not in x.stdout
    def p05():  # crypto params: decrypt w/ PBKDF2 200k + salt 16 header
        h, r = mk(side); r("set", "k", "value1")
        d, off = decrypt(h)
        return d is not None and "value1" not in open(os.path.join(h, ".vault", "vault.enc"), "rb").read().decode("latin1")
    def p06():  # salt random: two vaults differ in salt
        h1, r1 = mk(side); h2, r2 = mk(side); r1("set", "k", "v1234"); r2("set", "k", "v1234")
        _, o1 = decrypt(h1); _, o2 = decrypt(h2)
        b1 = open(os.path.join(h1, ".vault", "vault.enc"), "rb").read(); b2 = open(os.path.join(h2, ".vault", "vault.enc"), "rb").read()
        return o1 is not None and b1[o1:o1+16] != b2[o2:o2+16]
    def p07():  # invalid keys rejected exit 1
        h, r = mk(side)
        bad = ["bad-key", "a"*65, "spa ce", "k$", "é"]
        return all(r("set", k, "value1").returncode == 1 for k in bad) and r("set", "a"*64, "v").returncode == 0
    def p08():  # stored lowercase
        h, r = mk(side); r("set", "MyKey", "value1")
        d, _ = decrypt(h)
        return "mykey" in d and "MyKey" not in d and r("get", "MYKEY").stdout.strip() == "value1"
    def p09():  # 4096 bytes ok, 4097 rejected; multibyte counted in bytes
        h, r = mk(side)
        return (r("set", "a", "x"*4096).returncode == 0 and r("set", "b", "x"*4097).returncode == 1
                and r("set", "c", "é"*2049).returncode == 1 and r("set", "d", "é"*2048).returncode == 0)
    def p10():  # default ttl 90, ISO-8601
        h, r = mk(side); r("set", "k", "value1")
        d, _ = decrypt(h); e = datetime.fromisoformat(find_exp(d, "k"))
        if e.tzinfo is None: e = e.replace(tzinfo=timezone.utc)
        diff = (e - datetime.now(timezone.utc)).total_seconds() / 86400
        return 89.9 < diff < 90.1
    def p11():  # --ttl 5
        h, r = mk(side); r("set", "k", "value1", "--ttl", "5")
        d, _ = decrypt(h); e = datetime.fromisoformat(find_exp(d, "k"))
        if e.tzinfo is None: e = e.replace(tzinfo=timezone.utc)
        diff = (e - datetime.now(timezone.utc)).total_seconds() / 86400
        return 4.9 < diff < 5.1
    def p12():  # expired get -> 3, value not printed anywhere
        h, r = mk(side); r("set", "k", "expiredval"); set_expiry_past(h, "k")
        x = r("get", "k")
        return x.returncode == 3 and "expiredval" not in x.stdout + x.stderr
    def p13():  # list shows value[:4]*** never full
        h, r = mk(side); r("set", "k", "abcdefgh")
        x = r("list")
        return x.returncode == 0 and "abcd***" in x.stdout and "abcdefgh" not in x.stdout
    def p14():  # list with expired doesn't leak full value
        h, r = mk(side); r("set", "k", "expiredval"); set_expiry_past(h, "k")
        x = r("list"); return x.returncode == 0 and "expiredval" not in x.stdout
    def p15():  # list short value never full (value length <=4)
        h, r = mk(side); r("set", "k", "abc")
        x = r("list"); return x.returncode == 0 and "abc***" not in x.stdout
    def p16():  # rotate missing -> 1; existing -> 0 and new value
        h, r = mk(side); r("set", "k", "value1")
        return (r("rotate", "nope", "x").returncode == 1 and r("rotate", "k", "value2").returncode == 0
                and r("get", "k").stdout.strip() == "value2")
    def p17():  # delete
        h, r = mk(side); r("set", "k", "value1")
        return r("delete", "k").returncode == 0 and r("get", "k").returncode == 1 and r("delete", "k").returncode == 1
    def p18():  # audit appends & shows last 20
        h, r = mk(side)
        for i in range(25): r("set", "k%d" % i, "value%d" % i)
        x = r("audit"); log = open(os.path.join(h, ".vault", "audit.log")).read().splitlines()
        lines = [l for l in x.stdout.splitlines() if l.strip()]
        return x.returncode == 0 and len(lines) == 20 and len(log) >= 26 and lines == log[-20:]
    def p19():  # lockout after 3 wrong
        h, r = mk(side); r("set", "k", "value1")
        codes = [r("get", "k", pw="bad").returncode for _ in range(3)]
        lk = os.path.exists(os.path.join(h, ".vault", ".lockout"))
        after = r("get", "k")
        return codes == [2, 2, 2] and lk and after.returncode == 2 and "value1" not in after.stdout
    def p20():  # no values in audit log or stderr
        h, r = mk(side)
        r("set", "k", "SuperSecretXYZ"); g = r("get", "k"); r("rotate", "k", "OtherSecretQQQ")
        l = r("list"); e = r("set", "bad-key", "SuperSecretXYZ"); t = r("set", "k", "SuperSecretXYZ", "--ttl", "abc")
        log = open(os.path.join(h, ".vault", "audit.log")).read()
        errs = g.stderr + l.stderr + e.stderr + t.stderr
        return all(s not in log + errs for s in ["SuperSecretXYZ", "OtherSecretQQQ", "Supe", PW])
    def p21():  # perms
        h, r = mk(side); r("set", "k", "value1")
        f = stat.S_IMODE(os.stat(os.path.join(h, ".vault", "vault.enc")).st_mode)
        d = stat.S_IMODE(os.stat(os.path.join(h, ".vault")).st_mode)
        return f == 0o600 and d == 0o700
    def p22():  # perms after fixing loose dir
        h, r = mk(side); os.makedirs(os.path.join(h, ".vault"), mode=0o755); os.chmod(os.path.join(h, ".vault"), 0o755)
        r("set", "k", "value1")
        return stat.S_IMODE(os.stat(os.path.join(h, ".vault")).st_mode) == 0o700
    def p23():  # get missing key -> 1; unknown command -> 1
        h, r = mk(side); r("set", "k", "value1")
        return r("get", "zzz").returncode == 1 and r("frobnicate").returncode == 1
    def p24():  # bad ttl -> 1, no traceback
        h, r = mk(side)
        x = r("set", "k", "v", "--ttl", "abc"); y = r("set", "k", "v", "--ttl", "-5")
        return x.returncode == 1 and y.returncode == 1 and "Traceback" not in x.stderr + y.stderr
    def p25():  # correct pw resets attempt counter
        h, r = mk(side); r("set", "k", "value1")
        r("get", "k", pw="bad"); r("get", "k", pw="bad"); r("get", "k")
        x = r("get", "k", pw="bad")
        return x.returncode == 2 and not os.path.exists(os.path.join(h, ".vault", ".lockout"))
    for n, f in sorted(locals().items()):
        if n.startswith("p") and callable(f) and n[1:].isdigit(): P(n, f)
    return res
out = {"A": probes("A"), "B": probes("B")}
json.dump(out, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
