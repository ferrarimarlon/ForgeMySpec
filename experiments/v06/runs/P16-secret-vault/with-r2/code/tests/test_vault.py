import base64
import json
import os
import site
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault.py")
PW = "correct horse battery"
MAGIC = b"VLT1"


class VaultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = self._tmp.name

    # helpers
    def run_vault(self, *args, pw=PW, stdin="", home=None):
        env = {k: v for k, v in os.environ.items() if k != "VAULT_MASTER_KEY"}
        env["HOME"] = home or self.home
        env["PYTHONUSERBASE"] = site.getuserbase()  # keep user site-packages visible
        if pw is not None:
            env["VAULT_MASTER_KEY"] = pw
        return subprocess.run([sys.executable, VAULT, *args], env=env, input=stdin,
                              capture_output=True, text=True)

    def vdir(self, home=None):
        return os.path.join(home or self.home, ".vault")

    def blob(self, home=None):
        with open(os.path.join(self.vdir(home), "vault.enc"), "rb") as f:
            return f.read()

    def fernet(self, blob, pw=PW, iterations=200_000):
        salt = blob[4:20]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
        return Fernet(base64.urlsafe_b64encode(kdf.derive(pw.encode())))

    def read_data(self):
        b = self.blob()
        return json.loads(self.fernet(b).decrypt(b[20:]))

    def write_data(self, data):
        b = self.blob()
        token = self.fernet(b).encrypt(json.dumps(data).encode())
        with open(os.path.join(self.vdir(), "vault.enc"), "wb") as f:
            f.write(b[:20] + token)

    def audit_text(self):
        try:
            with open(os.path.join(self.vdir(), "audit.log")) as f:
                return f.read()
        except OSError:
            return ""

    def expire(self, key):
        data = self.read_data()
        data[key]["expires"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.write_data(data)

    # obligations
    def test_master_from_env(self):
        r = self.run_vault("set", "a", "v1", pw=None)
        self.assertEqual(r.returncode, 2)
        r = self.run_vault("set", "a", "v1", pw="")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.vdir(), ".lockout")))
        for flag in ("--password", "--master-key"):
            r = self.run_vault(flag, PW, "set", "a", "v1")
            self.assertEqual(r.returncode, 1)
            self.assertNotIn(PW, r.stderr)
        r = self.run_vault("set", "a", "v1")
        self.assertEqual(r.returncode, 0)

    def test_kdf_params(self):
        self.run_vault("set", "a", "v1")
        b = self.blob()
        self.assertEqual(json.loads(self.fernet(b).decrypt(b[20:]))["a"]["value"], "v1")
        from cryptography.fernet import InvalidToken
        with self.assertRaises(InvalidToken):
            self.fernet(b, iterations=199_999).decrypt(b[20:])

    def test_salt_header(self):
        self.run_vault("set", "a", "v1")
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        self.run_vault("set", "a", "v1", home=other.name)
        b1, b2 = self.blob(), self.blob(other.name)
        self.assertEqual(b1[:4], MAGIC)
        self.assertEqual(len(b1[4:20]), 16)
        self.assertNotEqual(b1[4:20], b2[4:20])
        salt = b1[4:20]
        self.run_vault("set", "b", "v2")
        self.assertEqual(self.blob()[4:20], salt)

    def test_key_lowercase(self):
        self.assertEqual(self.run_vault("set", "AbC_x9", "v1").returncode, 0)
        self.assertEqual(list(self.read_data()), ["abc_x9"])
        self.assertEqual(self.run_vault("get", "ABC_X9").stdout, "v1\n")
        self.assertEqual(self.run_vault("set", "A" * 64, "v").returncode, 0)
        for bad in ("a-b", "a b", "A" * 65, "", "é"):
            self.assertEqual(self.run_vault("set", bad, "v").returncode, 1, bad)

    def test_value_limit(self):
        self.assertEqual(self.run_vault("set", "a", "x" * 4096).returncode, 0)
        self.assertEqual(self.run_vault("get", "a").stdout, "x" * 4096 + "\n")
        self.assertEqual(self.run_vault("set", "b", "x" * 4097).returncode, 1)
        self.assertEqual(self.run_vault("set", "b", "é" * 2049).returncode, 1)
        self.assertEqual(self.run_vault("set", "b", "é" * 2048).returncode, 0)
        self.assertEqual(self.run_vault("set", "c", stdin="from stdin\n").returncode, 0)
        self.assertEqual(self.run_vault("get", "c").stdout, "from stdin\n")
        self.assertEqual(self.run_vault("set", "d", stdin="y" * 4097).returncode, 1)

    def test_ttl_default(self):
        self.run_vault("set", "a", "v1")
        self.run_vault("set", "b", "v1", "--ttl", "5")
        data = self.read_data()
        now = datetime.now(timezone.utc)
        for key, days in (("a", 90), ("b", 5)):
            exp = datetime.fromisoformat(data[key]["expires"])
            self.assertLess(abs(exp - (now + timedelta(days=days))), timedelta(minutes=5))
        for bad in ("0", "-1", "abc", "1.5"):
            self.assertEqual(self.run_vault("set", "c", "v", "--ttl", bad).returncode, 1, bad)

    def test_expiry_iso(self):
        self.run_vault("set", "a", "v1")
        exp = self.read_data()["a"]["expires"]
        self.assertIsInstance(exp, str)
        self.assertIsNotNone(datetime.fromisoformat(exp).tzinfo)

    def test_get_expired(self):
        self.run_vault("set", "a", "topsecretvalue")
        r = self.run_vault("get", "a")
        self.assertEqual((r.returncode, r.stdout), (0, "topsecretvalue\n"))
        self.expire("a")
        r = self.run_vault("get", "a")
        self.assertEqual(r.returncode, 3)
        self.assertNotIn("topsecretvalue", r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.run_vault("get", "missing").returncode, 1)

    def test_list_masked(self):
        self.run_vault("set", "k1", "supersecret")
        self.run_vault("set", "k2", "abc")
        self.run_vault("set", "k3", "abcd")
        self.run_vault("set", "k4", "gone-value")
        self.expire("k4")
        r = self.run_vault("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("supe***", r.stdout)
        self.assertNotIn("supersecret", r.stdout)
        rows = {l.split("\t")[0]: l.split("\t")[1] for l in r.stdout.splitlines()}
        self.assertEqual(rows["k2"], "ab***")
        self.assertEqual(rows["k3"], "abc***")
        self.assertEqual(rows["k4"], "[expired]")
        self.assertNotIn("gone", r.stdout)

    def test_rotate_missing(self):
        self.run_vault("set", "a", "old", "--ttl", "1")
        self.assertEqual(self.run_vault("rotate", "nope", "new").returncode, 1)
        self.assertNotIn("nope", self.read_data())
        self.assertEqual(self.run_vault("rotate", "a", "new").returncode, 0)
        self.assertEqual(self.run_vault("get", "a").stdout, "new\n")
        exp = datetime.fromisoformat(self.read_data()["a"]["expires"])
        self.assertGreater(exp, datetime.now(timezone.utc) + timedelta(days=80))
        self.assertEqual(self.run_vault("delete", "a").returncode, 0)
        self.assertEqual(self.run_vault("delete", "a").returncode, 1)

    def test_audit_tail(self):
        self.run_vault("set", "a", "v1")
        self.assertIn("set key=a exit=0", self.audit_text())
        with open(os.path.join(self.vdir(), "audit.log"), "w") as f:
            f.write("".join("line %d\n" % i for i in range(30)))
        r = self.run_vault("audit", pw=None)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 20)
        self.assertEqual(lines[0], "line 10")
        self.assertEqual(lines[-1], "line 29")

    def test_lockout(self):
        self.run_vault("set", "a", "v1")
        for _ in range(2):
            self.assertEqual(self.run_vault("get", "a", pw="wrong").returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.vdir(), ".lockout")))
        # a success resets the counter
        self.assertEqual(self.run_vault("get", "a").returncode, 0)
        for _ in range(2):
            self.assertEqual(self.run_vault("get", "a", pw="wrong").returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.vdir(), ".lockout")))
        self.assertEqual(self.run_vault("get", "a", pw="wrong").returncode, 2)
        self.assertTrue(os.path.exists(os.path.join(self.vdir(), ".lockout")))
        r = self.run_vault("get", "a")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.run_vault("set", "b", "v").returncode, 2)

    def test_no_value_leak(self):
        secret, big = "S3NTINEL-value-xyz", "B" * 5000
        pw = "pw-sentinel-123"
        runs = [
            self.run_vault("set", "a", secret, pw=pw),
            self.run_vault("get", "a", pw=pw),
            self.run_vault("list", pw=pw),
            self.run_vault("rotate", "a", secret + "2", pw=pw),
            self.run_vault("rotate", "zz", secret, pw=pw),
            self.run_vault("set", "a", big, pw=pw),
            self.run_vault("set", "bad key", secret, pw=pw),
            self.run_vault("set", "a", secret, "--ttl", "x", pw=pw),
            self.run_vault("get", "a", pw="wrong-" + secret),
            self.run_vault("delete", "a", pw=pw),
            self.run_vault("bogus", secret, pw=pw),
        ]
        for r in runs:
            self.assertNotIn(secret, r.stderr)
            self.assertNotIn(pw, r.stderr)
            self.assertNotIn(big, r.stderr)
        log = self.audit_text()
        for s in (secret, pw, big, "wrong-"):
            self.assertNotIn(s, log)
        self.assertIn("get key=a", log)

    def test_permissions(self):
        os.makedirs(self.vdir(), mode=0o755)
        os.chmod(self.vdir(), 0o755)
        self.run_vault("set", "a", "v1")
        mode = lambda p: stat.S_IMODE(os.stat(p).st_mode)
        self.assertEqual(mode(self.vdir()), 0o700)
        enc = os.path.join(self.vdir(), "vault.enc")
        self.assertEqual(mode(enc), 0o600)
        os.chmod(enc, 0o644)
        self.run_vault("rotate", "a", "v2")
        self.assertEqual(mode(enc), 0o600)
        self.assertEqual(mode(self.vdir()), 0o700)

    def test_exit_codes(self):
        self.assertEqual(self.run_vault("set", "a", "v1").returncode, 0)
        self.assertEqual(self.run_vault("get", "zzz").returncode, 1)
        self.assertEqual(self.run_vault("bogus").returncode, 1)
        self.assertEqual(self.run_vault().returncode, 1)
        self.assertEqual(self.run_vault("get", "a", pw="wrong").returncode, 2)
        self.expire("a")
        self.assertEqual(self.run_vault("get", "a").returncode, 3)


if __name__ == "__main__":
    unittest.main()
