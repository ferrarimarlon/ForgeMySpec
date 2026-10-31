import base64
import json
import os
import stat
import site
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.join(ROOT, "vault.py")
PW = "correct horse"
SECRET = "s3cr3tVALUE-xyz"


class VaultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = self._tmp.name
        self.vdir = os.path.join(self.home, ".vault")

    def run_vault(self, *args, pw=PW, stdin=None):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self.home,
               "PYTHONUSERBASE": site.getuserbase()}
        if pw is not None:
            env["VAULT_MASTER_KEY"] = pw
        return subprocess.run([sys.executable, VAULT, *args], env=env,
                              input=stdin, capture_output=True, text=True)

    def decrypt(self, pw=PW):
        with open(os.path.join(self.vdir, "vault.enc"), "rb") as f:
            blob = f.read()
        salt, token = blob[:16], blob[16:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000)
        f = Fernet(base64.urlsafe_b64encode(kdf.derive(pw.encode())))
        return json.loads(f.decrypt(token))

    def audit_text(self):
        with open(os.path.join(self.vdir, "audit.log")) as f:
            return f.read()

    def test_master_key_env_only(self):
        r = self.run_vault("set", "a", "v", pw=None)
        self.assertEqual(r.returncode, 1)
        r = self.run_vault("set", "a", "v", pw="")
        self.assertEqual(r.returncode, 1)
        # no CLI option can carry a password
        r = self.run_vault("--password", "x", "list")
        self.assertEqual(r.returncode, 1)
        r = self.run_vault("set", "a", "v", "--master-key", PW)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.run_vault("set", "a", "v").returncode, 0)

    def test_kdf_and_salt(self):
        with open(VAULT) as f:
            src = f.read()
        self.assertIn("PBKDF2HMAC", src)
        self.assertIn("hashes.SHA256()", src)
        self.assertIn("200000", src)
        self.assertEqual(self.run_vault("set", "a", SECRET).returncode, 0)
        self.assertEqual(self.decrypt()["a"]["value"], SECRET)  # 200000 iters, SHA-256, header salt
        with open(os.path.join(self.vdir, "vault.enc"), "rb") as f:
            salt1 = f.read(16)
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        env = {"PATH": os.environ["PATH"], "HOME": other.name, "VAULT_MASTER_KEY": PW,
               "PYTHONUSERBASE": site.getuserbase()}
        subprocess.run([sys.executable, VAULT, "set", "a", "v"], env=env, check=True)
        with open(os.path.join(other.name, ".vault", "vault.enc"), "rb") as f:
            salt2 = f.read(16)
        self.assertEqual(len(salt1), 16)
        self.assertNotEqual(salt1, salt2)

    def test_key_validation_lowercase(self):
        for bad in ["", "a-b", "a b", "ä", "x" * 65, "a.b"]:
            r = self.run_vault("set", bad, "v")
            self.assertEqual(r.returncode, 1, bad)
        self.assertEqual(self.run_vault("set", "x" * 64, "v").returncode, 0)
        self.assertEqual(self.run_vault("set", "FooBar_1", "v").returncode, 0)
        self.assertIn("foobar_1", self.decrypt())
        self.assertNotIn("FooBar_1", self.decrypt())
        r = self.run_vault("get", "FOOBAR_1")
        self.assertEqual((r.returncode, r.stdout), (0, "v\n"))

    def test_value_size_limit(self):
        self.assertEqual(self.run_vault("set", "a", "x" * 4096).returncode, 0)
        r = self.run_vault("set", "b", "x" * 4097)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("xxxxx", r.stderr)
        # 2049 two-byte characters = 4098 bytes
        self.assertEqual(self.run_vault("set", "c", "é" * 2049).returncode, 1)
        self.assertEqual(self.run_vault("set", "d", "é" * 2048).returncode, 0)

    def test_ttl_default_and_iso(self):
        self.run_vault("set", "a", "v")
        self.run_vault("set", "b", "v", "--ttl", "5")
        data = self.decrypt()
        now = datetime.now(timezone.utc)
        ea = datetime.fromisoformat(data["a"]["expires"])
        eb = datetime.fromisoformat(data["b"]["expires"])
        self.assertLess(abs(ea - (now + timedelta(days=90))), timedelta(minutes=5))
        self.assertLess(abs(eb - (now + timedelta(days=5))), timedelta(minutes=5))
        self.assertEqual(self.run_vault("set", "c", "v", "--ttl", "abc").returncode, 1)
        self.assertEqual(self.run_vault("set", "c", "v", "--ttl", "-1").returncode, 1)

    def test_get_value_only(self):
        self.run_vault("set", "a", SECRET)
        r = self.run_vault("get", "a")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, SECRET + "\n", ""))
        self.assertEqual(self.run_vault("get", "missing").returncode, 1)

    def test_expired_exit_3(self):
        self.run_vault("set", "a", SECRET, "--ttl", "0")
        r = self.run_vault("get", "a")
        self.assertEqual(r.returncode, 3)
        self.assertNotIn(SECRET, r.stdout)
        self.assertNotIn(SECRET, r.stderr)
        self.assertEqual(r.stdout, "")

    def test_list_masks_value(self):
        self.run_vault("set", "a", SECRET)
        self.run_vault("set", "b", "ab")
        r = self.run_vault("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("s3cr***", r.stdout)
        self.assertNotIn(SECRET, r.stdout)
        self.assertNotIn("s3cr3", r.stdout)
        for line in r.stdout.splitlines():
            if line.startswith("b\t"):
                self.assertNotIn("ab***", line)  # short values are never shown whole

    def test_delete_and_rotate(self):
        self.run_vault("set", "a", "old")
        r = self.run_vault("rotate", "a", "new", "--ttl", "10")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.run_vault("get", "a").stdout, "new\n")
        self.assertEqual(self.run_vault("rotate", "nope", "x").returncode, 1)
        self.assertNotIn("nope", self.decrypt())
        self.assertEqual(self.run_vault("delete", "a").returncode, 0)
        self.assertEqual(self.run_vault("get", "a").returncode, 1)
        self.assertEqual(self.run_vault("delete", "a").returncode, 1)

    def test_audit_last_20(self):
        for i in range(25):
            self.run_vault("set", "k%d" % i, "v")
        r = self.run_vault("audit")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout.splitlines()), 20)
        self.assertGreaterEqual(len(self.audit_text().splitlines()), 26)
        self.assertIn("audit", r.stdout.splitlines()[-1])
        self.assertNotIn("\tk0\t", r.stdout)

    def test_no_value_leak(self):
        outs = [self.run_vault("set", "a", SECRET), self.run_vault("get", "a"),
                self.run_vault("rotate", "a", SECRET + "2"),
                self.run_vault("set", "b", SECRET, "--ttl", "0"),
                self.run_vault("get", "b"), self.run_vault("get", "a", pw="wrong"),
                self.run_vault("set", "bad key", SECRET),
                self.run_vault("rotate", "zzz", SECRET), self.run_vault("audit")]
        log = self.audit_text()
        self.assertNotIn(SECRET, log)
        for r in outs:
            self.assertNotIn(SECRET, r.stderr)
        self.assertNotIn(SECRET, outs[-1].stdout)

    def test_lockout_after_three(self):
        self.run_vault("set", "a", "v")
        lock = os.path.join(self.vdir, ".lockout")
        for i in range(2):
            r = self.run_vault("get", "a", pw="wrong")
            self.assertEqual(r.returncode, 2)
            self.assertFalse(os.path.exists(lock))
        r = self.run_vault("get", "a", pw="wrong")
        self.assertEqual(r.returncode, 2)
        self.assertTrue(os.path.exists(lock))
        r = self.run_vault("get", "a")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_correct_password_resets_failures(self):
        self.run_vault("set", "a", "v")
        self.run_vault("get", "a", pw="wrong")
        self.run_vault("get", "a", pw="wrong")
        self.assertEqual(self.run_vault("get", "a").returncode, 0)
        self.run_vault("get", "a", pw="wrong")
        self.run_vault("get", "a", pw="wrong")
        self.assertFalse(os.path.exists(os.path.join(self.vdir, ".lockout")))

    def test_file_permissions(self):
        self.run_vault("set", "a", "v")
        self.run_vault("rotate", "a", "w")
        mode = lambda p: stat.S_IMODE(os.stat(p).st_mode)
        self.assertEqual(mode(self.vdir), 0o700)
        self.assertEqual(mode(os.path.join(self.vdir, "vault.enc")), 0o600)


if __name__ == "__main__":
    unittest.main()
