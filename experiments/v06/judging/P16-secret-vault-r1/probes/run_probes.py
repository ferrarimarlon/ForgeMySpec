"""Black-box probes for vault.py. Usage: python3 run_probes.py <path/to/vault.py>"""
import base64, json, os, re, stat, subprocess, sys, tempfile, site
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT = os.path.abspath(sys.argv[1])
PW = "pw-Correct-1"
SECRET = "SuperSecretValue123"

def new_home():
    return tempfile.mkdtemp(prefix="vprobe")

def run(home, *args, pw=PW, stdin=None):
    env = {"PATH": os.environ["PATH"], "HOME": home, "PYTHONUSERBASE": site.getuserbase()}
    if pw is not None:
        env["VAULT_MASTER_KEY"] = pw
    return subprocess.run([sys.executable, VAULT, *args], env=env, input=stdin,
                          capture_output=True, text=True, timeout=60)

def fernet(pw, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(pw.encode())))

def decrypt(home, pw=PW):
    """Try salt at small header offsets; return (prefix, salt, data) or None."""
    blob = open(os.path.join(home, ".vault", "vault.enc"), "rb").read()
    for off in range(0, 9):
        salt = blob[off:off + 16]; tok = blob[off + 16:]
        try:
            return blob[:off], salt, json.loads(fernet(pw, salt).decrypt(tok))
        except (InvalidToken, ValueError):
            continue
    return None

def reencrypt(home, prefix, salt, data, pw=PW):
    p = os.path.join(home, ".vault", "vault.enc")
    with open(p, "wb") as f:
        f.write(prefix + salt + fernet(pw, salt).encrypt(json.dumps(data).encode()))

def expire_key(home, key):
    prefix, salt, data = decrypt(home)
    data[key]["expires"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    reencrypt(home, prefix, salt, data)

def audit_text(home):
    try: return open(os.path.join(home, ".vault", "audit.log")).read()
    except OSError: return ""

P = {}
def probe(pid):
    def deco(fn):
        try: P[pid] = "pass" if fn() else "fail"
        except Exception as e: P[pid] = "fail"; print(pid, "EXC", repr(e), file=sys.stderr)
        return fn
    return deco

@probe("P01_env_password_only")
def _():
    h = new_home()
    r1 = run(h, "set", "a", "v", pw=None)
    r2 = run(h, "--password", PW, "list", pw=None)
    r3 = run(h, "set", "a", "v")
    return r1.returncode != 0 and r2.returncode != 0 and r3.returncode == 0

@probe("P02_kdf_fernet_salt16_header")
def _():
    h = new_home(); run(h, "set", "a", SECRET)
    d = decrypt(h)
    return d is not None and len(d[1]) == 16 and SECRET in json.dumps(d[2])

@probe("P03_salt_random")
def _():
    h1, h2 = new_home(), new_home()
    run(h1, "set", "a", "v"); run(h2, "set", "a", "v")
    return decrypt(h1)[1] != decrypt(h2)[1]

@probe("P04_invalid_keys_rejected")
def _():
    h = new_home()
    bad = ["a-b", "a b", "", "x" * 65, "é", "a.b"]
    return all(run(h, "set", k, "v").returncode == 1 for k in bad) and run(h, "set", "x" * 64, "v").returncode == 0

@probe("P05_key_lowercased")
def _():
    h = new_home(); run(h, "set", "MyKey", "val1")
    r = run(h, "get", "mykey"); r2 = run(h, "get", "MYKEY")
    d = decrypt(h)[2]
    return r.stdout.strip() == "val1" and r2.stdout.strip() == "val1" and "mykey" in d and "MyKey" not in d

@probe("P06_value_4096_limit")
def _():
    h = new_home()
    ok = run(h, "set", "a", "x" * 4096).returncode == 0
    bad = run(h, "set", "b", "x" * 4097).returncode == 1
    bad_mb = run(h, "set", "c", "é" * 2049).returncode == 1  # 4098 bytes
    ok_mb = run(h, "set", "d", "é" * 2048).returncode == 0
    return ok and bad and bad_mb and ok_mb

@probe("P07_ttl_default_90_iso")
def _():
    h = new_home(); run(h, "set", "a", "v")
    e = decrypt(h)[2]["a"]
    exp = [v for v in e.values() if isinstance(v, str) and re.match(r"\d{4}-\d\d-\d\dT", v)]
    if not exp: return False
    dt = datetime.fromisoformat(exp[0])
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400
    return 89.9 < days < 90.1

@probe("P08_ttl_option")
def _():
    h = new_home(); r = run(h, "set", "a", "v", "--ttl", "7")
    e = decrypt(h)[2]["a"]
    exp = [v for v in e.values() if isinstance(v, str) and re.match(r"\d{4}-\d\d-\d\dT", v)]
    dt = datetime.fromisoformat(exp[0])
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400
    return r.returncode == 0 and 6.9 < days < 7.1

@probe("P09_get_prints_only_value")
def _():
    h = new_home(); run(h, "set", "a", SECRET)
    r = run(h, "get", "a")
    return r.returncode == 0 and r.stdout in (SECRET, SECRET + "\n")

@probe("P10_get_expired_exit3_no_value")
def _():
    h = new_home(); run(h, "set", "a", SECRET); expire_key(h, "a")
    r = run(h, "get", "a")
    return r.returncode == 3 and SECRET not in r.stdout + r.stderr

@probe("P11_list_masks")
def _():
    h = new_home(); run(h, "set", "a", SECRET)
    r = run(h, "list")
    return r.returncode == 0 and SECRET[:4] + "***" in r.stdout and SECRET not in r.stdout and SECRET[:5] not in r.stdout

@probe("P12_list_expired_no_full_value")
def _():
    h = new_home(); run(h, "set", "a", SECRET); expire_key(h, "a")
    r = run(h, "list")
    return r.returncode == 0 and SECRET not in r.stdout + r.stderr

@probe("P13_rotate_missing_exit1")
def _():
    h = new_home(); run(h, "set", "a", "v")
    return run(h, "rotate", "nokey", "x").returncode == 1

@probe("P14_rotate_existing")
def _():
    h = new_home(); run(h, "set", "a", "old")
    r = run(h, "rotate", "a", "new")
    return r.returncode == 0 and run(h, "get", "a").stdout.strip() == "new"

@probe("P15_delete")
def _():
    h = new_home(); run(h, "set", "a", "v")
    r = run(h, "delete", "a"); g = run(h, "get", "a"); d2 = run(h, "delete", "a")
    return r.returncode == 0 and g.returncode == 1 and d2.returncode == 1

@probe("P16_audit_appends_and_tail20")
def _():
    h = new_home()
    for i in range(25): run(h, "set", "k%d" % i, "v")
    before = audit_text(h).count("\n")
    r = run(h, "audit")
    after = audit_text(h).count("\n")
    lines = r.stdout.splitlines()
    return r.returncode == 0 and after > before and len(lines) == 20 and lines == audit_text(h).splitlines()[-20:]

@probe("P17_lockout_after_3")
def _():
    h = new_home(); run(h, "set", "a", "v")
    codes = [run(h, "list", pw="wrong").returncode for _ in range(3)]
    lock = os.path.exists(os.path.join(h, ".vault", ".lockout"))
    good = run(h, "get", "a")
    return codes == [2, 2, 2] and lock and good.returncode == 2 and "v" != good.stdout.strip()

@probe("P18_wrong_password_exit2_no_lock_after_1")
def _():
    h = new_home(); run(h, "set", "a", "v")
    r = run(h, "get", "a", pw="wrong")
    return r.returncode == 2 and not os.path.exists(os.path.join(h, ".vault", ".lockout"))

@probe("P19_no_values_in_audit_or_stderr")
def _():
    h = new_home(); err = ""
    for args in (["set", "a", SECRET], ["get", "a"], ["list"], ["rotate", "a", SECRET + "2"],
                 ["get", "a"], ["set", "b", SECRET + "3", "--ttl", "bogus"], ["get", "b", SECRET],
                 ["set", "bad-key", SECRET], ["audit"], ["delete", "a"]):
        err += run(h, *args).stderr
    r = run(h, "set", "c", SECRET + "4"); err += r.stderr
    run(h, "get", "c", pw="wrong")
    a = audit_text(h)
    return SECRET not in a and SECRET not in err

@probe("P20_permissions")
def _():
    h = new_home(); run(h, "set", "a", "v")
    d = stat.S_IMODE(os.stat(os.path.join(h, ".vault")).st_mode)
    f = stat.S_IMODE(os.stat(os.path.join(h, ".vault", "vault.enc")).st_mode)
    return d == 0o700 and f == 0o600

@probe("P21_permissions_after_rotate_delete")
def _():
    h = new_home(); run(h, "set", "a", "v"); run(h, "set", "b", "v")
    run(h, "rotate", "a", "w"); run(h, "delete", "b")
    f = stat.S_IMODE(os.stat(os.path.join(h, ".vault", "vault.enc")).st_mode)
    return f == 0o600

@probe("P22_usage_errors_exit1")
def _():
    h = new_home()
    return all(run(h, *a).returncode == 1 for a in (["bogus"], [], ["get"], ["set", "a", "v", "--ttl", "x"]))

@probe("P23_get_missing_exit1")
def _():
    h = new_home(); run(h, "set", "a", "v")
    return run(h, "get", "zz").returncode == 1

@probe("P24_set_stdin_value")
def _():
    h = new_home(); r = run(h, "set", "a", stdin=SECRET + "\n")
    return r.returncode == 0 and run(h, "get", "a").stdout.strip() == SECRET

print(json.dumps(P))
