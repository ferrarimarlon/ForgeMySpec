import base64, json, os, site, stat, subprocess, sys, tempfile, shutil
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "master-pw-123"
SECRET = "SuperSecretValue987"

def run(side, home, *args, pw=PW, stdin=""):
    env = {k: v for k, v in os.environ.items() if k != "VAULT_MASTER_KEY"}
    env["HOME"] = home
    env["PYTHONUSERBASE"] = site.getuserbase()
    if pw is not None:
        env["VAULT_MASTER_KEY"] = pw
    return subprocess.run([sys.executable, os.path.join(ROOT, side, "vault.py"), *args],
                          env=env, input=stdin, capture_output=True, text=True, timeout=60)

def vdir(h): return os.path.join(h, ".vault")

def find_layout(blob, pw=PW, iters=200_000):
    # locate a 16-byte salt within a small header and decrypt the remainder
    for off in range(0, 17):
        salt = blob[off:off+16]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters)
        f = Fernet(base64.urlsafe_b64encode(kdf.derive(pw.encode())))
        try:
            return off, f, json.loads(f.decrypt(blob[off+16:]))
        except (InvalidToken, ValueError):
            continue
    return None

def full_text(home):
    out = ""
    for root, _, files in os.walk(vdir(home)):
        for fn in files:
            if fn == "vault.enc": continue
            with open(os.path.join(root, fn), "rb") as fh:
                out += fh.read().decode("utf-8", "replace")
    return out

def probes(side):
    R = {}
    def new():
        return tempfile.mkdtemp(prefix=f"vp{side}")
    def P(pid, cond):
        R[pid] = "pass" if cond else "fail"

    h = new()
    r = run(side, h, "set", "MyKey", SECRET)
    P("P01_set_ok", r.returncode == 0)
    r = run(side, h, "get", "mykey")
    P("P02_get_lowercase_value_only", r.returncode == 0 and r.stdout.strip() == SECRET and r.stdout.rstrip("\n") == SECRET)
    r2 = run(side, h, "get", "MYKEY")
    P("P03_get_case_insensitive", r2.returncode == 0 and r2.stdout.strip() == SECRET)
    blob = open(os.path.join(vdir(h), "vault.enc"), "rb").read()
    P("P04_no_plaintext_in_file", SECRET.encode() not in blob)
    lay = find_layout(blob)
    P("P05_pbkdf2_200k_fernet_salt16_header", lay is not None)
    if lay:
        s = json.dumps(lay[2])
        P("P06_key_stored_lowercase", "mykey" in s and "MyKey" not in s)
        # find ISO expiry
        iso_ok = False; ttl_ok = False
        for m in __import__("re").findall(r'"(\d{4}-\d\d-\d\dT[^"]+)"', s):
            try:
                d = datetime.fromisoformat(m)
                if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
                iso_ok = True
                days = (d - datetime.now(timezone.utc)).total_seconds() / 86400
                ttl_ok = ttl_ok or (89.9 < days < 90.1)
            except ValueError: pass
        P("P07_expiry_iso8601", iso_ok)
        P("P08_default_ttl_90", ttl_ok)
    else:
        for p in ("P06_key_stored_lowercase", "P07_expiry_iso8601", "P08_default_ttl_90"): R[p] = "fail"
    # salt randomness
    h2 = new(); run(side, h2, "set", "a", "x12345")
    b2 = open(os.path.join(vdir(h2), "vault.enc"), "rb").read()
    lay2 = find_layout(b2)
    P("P09_salt_random", lay and lay2 and blob[lay[0]:lay[0]+16] != b2[lay2[0]:lay2[0]+16])
    # ttl
    h3 = new(); r = run(side, h3, "set", "t", "value1", "--ttl", "5")
    lay3 = find_layout(open(os.path.join(vdir(h3), "vault.enc"), "rb").read()) if r.returncode == 0 else None
    ok = False
    if lay3:
        s = json.dumps(lay3[2])
        for m in __import__("re").findall(r'"(\d{4}-\d\d-\d\dT[^"]+)"', s):
            d = datetime.fromisoformat(m)
            if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
            ok = ok or 4.9 < (d - datetime.now(timezone.utc)).total_seconds()/86400 < 5.1
    P("P10_ttl_option", ok)
    # perms
    st = os.stat(os.path.join(vdir(h), "vault.enc")).st_mode
    P("P11_vault_enc_600", stat.S_IMODE(st) == 0o600)
    P("P12_dir_700", stat.S_IMODE(os.stat(vdir(h)).st_mode) == 0o700)
    # invalid keys
    P("P13_invalid_key_char", run(side, h, "set", "bad-key", "v").returncode == 1)
    P("P14_key_too_long", run(side, h, "set", "a"*65, "v").returncode == 1)
    P("P15_key_64_ok", run(side, h, "set", "a"*64, "v").returncode == 0)
    # value size
    P("P16_value_4096_ok", run(side, h, "set", "big", "é"*2048).returncode == 0)
    r = run(side, h, "set", "big2", "é"*2048 + "x")
    P("P17_value_4097_rejected", r.returncode == 1)
    # list
    r = run(side, h, "list")
    P("P18_list_masks", r.returncode == 0 and SECRET[:4] + "***" in r.stdout and SECRET not in r.stdout
      and "é"*2048 not in r.stdout)
    # missing
    P("P19_get_missing_exit1", run(side, h, "get", "nokey").returncode == 1)
    P("P20_rotate_missing_exit1", run(side, h, "rotate", "nokey", "zzz123").returncode == 1)
    r = run(side, h, "rotate", "mykey", "NewValue456")
    P("P21_rotate_existing", r.returncode == 0 and run(side, h, "get", "mykey").stdout.strip() == "NewValue456")
    r = run(side, h, "delete", "mykey")
    P("P22_delete", r.returncode == 0 and run(side, h, "get", "mykey").returncode == 1)
    P("P23_delete_missing_exit1", run(side, h, "delete", "mykey").returncode == 1)
    # audit
    run(side, h, "set", "auditkey", SECRET)
    run(side, h, "get", "auditkey")
    r = run(side, h, "audit")
    logp = os.path.join(vdir(h), "audit.log")
    P("P24_audit_log_exists", os.path.exists(logp) and os.path.getsize(logp) > 0)
    P("P25_audit_shows_lines", r.returncode == 0 and "auditkey" in r.stdout)
    P("P26_no_values_in_audit_or_files", SECRET not in full_text(h) and "NewValue456" not in full_text(h)
      and SECRET not in r.stdout)
    for i in range(30): run(side, h, "get", f"k{i}")
    r = run(side, h, "audit")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    P("P27_audit_last_20", r.returncode == 0 and len(lines) == 20)
    # expiry: rewrite entry expiry into the past
    he = new(); run(side, he, "set", "exp", SECRET)
    p = os.path.join(vdir(he), "vault.enc"); b = open(p, "rb").read(); lay = find_layout(b)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    s = json.dumps(lay[2]); import re
    s = re.sub(r'"\d{4}-\d\d-\d\dT[^"]+"', json.dumps(past), s)
    open(p, "wb").write(b[:lay[0]+16] + lay[1].encrypt(s.encode()))
    r = run(side, he, "get", "exp")
    P("P28_expired_exit3_no_value", r.returncode == 3 and SECRET not in r.stdout and SECRET not in r.stderr)
    r = run(side, he, "list")
    P("P29_list_expired_no_value", SECRET not in r.stdout)
    # auth
    hl = new(); run(side, hl, "set", "k", SECRET)
    r = run(side, hl, "get", "k", pw="wrong")
    P("P30_wrong_pw_exit2", r.returncode == 2 and SECRET not in r.stdout + r.stderr)
    run(side, hl, "get", "k", pw="wrong"); run(side, hl, "get", "k", pw="wrong")
    P("P31_lockout_file_created", os.path.exists(os.path.join(vdir(hl), ".lockout")))
    r = run(side, hl, "get", "k")
    P("P32_locked_correct_pw_exit2", r.returncode == 2 and SECRET not in r.stdout)
    # missing env
    hm = new(); r = run(side, hm, "set", "k", "v1234", pw=None)
    P("P33_missing_env_nonzero", r.returncode in (1, 2) and not os.path.exists(os.path.join(vdir(hm), "vault.enc")))
    # no --password style arg accepted
    r = run(side, hm, "get", "k", "--password", PW, pw=None)
    P("P34_no_password_cli_arg", r.returncode != 0)
    # stderr never shows values (stray extra arg)
    hs = new(); r = run(side, hs, "set", "k", "part1", "LeakedTailValue")
    P("P35_stderr_no_value_on_usage_error", "LeakedTailValue" not in r.stderr)
    r = run(side, hs, "set", "k2", "x"*5000)
    P("P36_stderr_no_value_on_oversize", "x"*100 not in r.stderr)
    # stdin value
    r = run(side, hs, "set", "si", stdin="FromStdin99\n")
    P("P37_unknown_command_exit1", run(side, hs, "frobnicate").returncode == 1)
    for d in (h, h2, h3, he, hl, hm, hs): shutil.rmtree(d, ignore_errors=True)
    return R

res = {s: probes(s) for s in ("A", "B")}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for pid in res["A"]:
    print(f"{pid:42} A={res['A'][pid]:5} B={res['B'][pid]}")
