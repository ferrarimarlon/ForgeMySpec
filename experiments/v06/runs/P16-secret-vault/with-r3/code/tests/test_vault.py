import base64
import site
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT = str(Path(__file__).resolve().parent.parent / "vault.py")
PW = "correct horse"


class VaultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = self._tmp.name
        self.vdir = Path(self.home) / ".vault"

    def run_vault(self, *args, pw=PW, env_extra=None):
        env = {k: v for k, v in os.environ.items() if k != "VAULT_MASTER_KEY"}
        env["HOME"] = self.home
        env["PYTHONUSERBASE"] = site.getuserbase()
        if pw is not None:
            env["VAULT_MASTER_KEY"] = pw
        if env_extra:
            env.update(env_extra)
        return subprocess.run([sys.executable, VAULT, *args], env=env,
                              capture_output=True, text=True)

    def mode(self, p):
        return stat.S_IMODE(os.stat(p).st_mode)

    def test_master_key_env_only(self):
        r = self.run_vault("set", "a", "v", pw=None)
        self.assertEqual(r.returncode, 2)
        r = self.run_vault("set", "a", "v", "--password", "x")
        self.assertEqual(r.returncode, 1)
        r = self.run_vault("--help")
        self.assertNotIn("--password", r.stdout)
        self.assertIn("VAULT_MASTER_KEY", r.stdout)
        self.assertEqual(self.run_vault("set", "a", "v").returncode, 0)

    def test_kdf_and_salt(self):
        self.run_vault("set", "a", "supersecretvalue")
        blob = (self.vdir / "vault.enc").read_bytes()
        salt, token = blob[:16], blob[16:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
        key = base64.urlsafe_b64encode(kdf.derive(PW.encode()))
        data = json.loads(Fernet(key).decrypt(token))
        self.assertEqual(data["a"]["value"], "supersecretvalue")
        self.assertNotIn(b"supersecretvalue", blob)
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        env = {**os.environ, "HOME": other.name, "VAULT_MASTER_KEY": PW,
               "PYTHONUSERBASE": site.getuserbase()}
        subprocess.run([sys.executable, VAULT, "set", "a", "x"], env=env, capture_output=True)
        blob2 = (Path(other.name) / ".vault" / "vault.enc").read_bytes()
        self.assertNotEqual(salt, blob2[:16])

    def test_key_validation(self):
        for bad in ["", "a-b", "a b", "x" * 65, "ключ", "a.b"]:
            self.assertEqual(self.run_vault("set", bad, "v").returncode, 1, bad)
        self.assertEqual(self.run_vault("set", "x" * 64, "v").returncode, 0)
        self.assertEqual(self.run_vault("set", "Foo_1", "bar").returncode, 0)
        r = self.run_vault("get", "FOO_1")
        self.assertEqual((r.returncode, r.stdout), (0, "bar\n"))
        self.assertIn("foo_1", self.run_vault("list").stdout)
        self.assertNotIn("Foo_1", self.run_vault("list").stdout)

    def test_value_size_limit(self):
        self.assertEqual(self.run_vault("set", "k", "a" * 4096).returncode, 0)
        self.assertEqual(self.run_vault("set", "k", "a" * 4097).returncode, 1)
        # 2049 two-byte characters = 4098 bytes but only 2049 characters
        self.assertEqual(self.run_vault("set", "k", "é" * 2049).returncode, 1)
        self.assertEqual(self.run_vault("set", "k", "é" * 2048).returncode, 0)

    def _entries(self):
        blob = (self.vdir / "vault.enc").read_bytes()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=blob[:16], iterations=200_000)
        key = base64.urlsafe_b64encode(kdf.derive(PW.encode()))
        return json.loads(Fernet(key).decrypt(blob[16:]))

    def test_ttl_iso_default(self):
        before = datetime.now(timezone.utc)
        self.run_vault("set", "d", "v")
        self.run_vault("set", "t", "v", "--ttl", "5")
        e = self._entries()
        d = datetime.fromisoformat(e["d"]["expires"])
        t = datetime.fromisoformat(e["t"]["expires"])
        self.assertLess(abs(d - (before + timedelta(days=90))), timedelta(minutes=5))
        self.assertLess(abs(t - (before + timedelta(days=5))), timedelta(minutes=5))
        for bad in ["abc", "-1", "1.5"]:
            self.assertEqual(self.run_vault("set", "x", "v", "--ttl", bad).returncode, 1, bad)

    def test_get_value_only(self):
        self.run_vault("set", "k", "hello world")
        r = self.run_vault("get", "k")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "hello world\n", ""))
        self.assertEqual(self.run_vault("get", "nope").returncode, 1)

    def test_expired_exit_3(self):
        self.run_vault("set", "k", "topsecretvalue", "--ttl", "0")
        r = self.run_vault("get", "k")
        self.assertEqual(r.returncode, 3)
        self.assertNotIn("topsecretvalue", r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_list_masks_values(self):
        self.run_vault("set", "alpha", "abcdefghij")
        self.run_vault("set", "old", "zyxwvutsrq", "--ttl", "0")
        r = self.run_vault("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("alpha  abcd***", r.stdout)
        self.assertNotIn("abcdefghij", r.stdout)
        self.assertNotIn("zyxw", r.stdout)
        self.assertIn("old  expired", r.stdout)

    def test_commands_roundtrip(self):
        self.assertEqual(self.run_vault("set", "k", "one").returncode, 0)
        self.assertEqual(self.run_vault("get", "k").stdout, "one\n")
        self.assertEqual(self.run_vault("rotate", "k", "two", "--ttl", "10").returncode, 0)
        self.assertEqual(self.run_vault("get", "k").stdout, "two\n")
        self.assertEqual(self.run_vault("delete", "k").returncode, 0)
        self.assertEqual(self.run_vault("get", "k").returncode, 1)
        self.assertEqual(self.run_vault("delete", "k").returncode, 1)
        # rotate resets expiry of an expired entry
        self.run_vault("set", "e", "old", "--ttl", "0")
        self.assertEqual(self.run_vault("get", "e").returncode, 3)
        self.run_vault("rotate", "e", "new")
        self.assertEqual(self.run_vault("get", "e").stdout, "new\n")

    def test_rotate_missing_exit_1(self):
        self.run_vault("set", "other", "v")
        r = self.run_vault("rotate", "ghost", "v2")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.run_vault("get", "ghost").returncode, 1)

    def test_audit_tail(self):
        for i in range(30):
            self.run_vault("set", "k%d" % i, "v")
        r = self.run_vault("audit")
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 20)
        self.assertIn("audit", lines[-1])
        total = (self.vdir / "audit.log").read_text().splitlines()
        self.assertEqual(len(total), 31)
        self.assertEqual(lines, total[-20:])

    def test_no_values_leak(self):
        sec = "SUPERSECRET_9876"
        outs = [
            self.run_vault("set", "k", sec),
            self.run_vault("get", "k"),
            self.run_vault("rotate", "k", sec + "2"),
            self.run_vault("set", "bad key", sec),
            self.run_vault("rotate", "ghost", sec),
            self.run_vault("set", "k", sec * 1000),
            self.run_vault("set", "k", sec, "--ttl", "x"),
            self.run_vault("set", "k", sec, pw="wrong"),
            self.run_vault("list"),
            self.run_vault("audit"),
        ]
        for r in outs:
            self.assertNotIn(sec, r.stderr)
        log = (self.vdir / "audit.log").read_text()
        self.assertNotIn(sec, log)
        self.assertNotIn(sec, outs[-1].stdout)

    def test_lockout_after_three(self):
        self.run_vault("set", "k", "v")
        self.assertEqual(self.run_vault("get", "k", pw="bad").returncode, 2)
        self.assertEqual(self.run_vault("get", "k", pw="bad").returncode, 2)
        # a correct password resets the counter
        self.assertEqual(self.run_vault("get", "k").returncode, 0)
        self.assertEqual(self.run_vault("get", "k", pw="bad").returncode, 2)
        self.assertEqual(self.run_vault("get", "k", pw="bad").returncode, 2)
        self.assertFalse((self.vdir / ".lockout").exists())
        r = self.run_vault("get", "k", pw="bad")
        self.assertEqual(r.returncode, 2)
        self.assertTrue((self.vdir / ".lockout").exists())
        r = self.run_vault("get", "k")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_file_modes(self):
        self.vdir.mkdir(mode=0o755)
        os.chmod(self.vdir, 0o755)
        self.run_vault("set", "k", "v")
        self.assertEqual(self.mode(self.vdir), 0o700)
        self.assertEqual(self.mode(self.vdir / "vault.enc"), 0o600)
        self.run_vault("rotate", "k", "w")
        self.assertEqual(self.mode(self.vdir / "vault.enc"), 0o600)

    def test_exit_code_map(self):
        self.assertEqual(self.run_vault("set", "k", "v").returncode, 0)
        self.assertEqual(self.run_vault("get", "zzz").returncode, 1)
        self.assertEqual(self.run_vault("bogus").returncode, 1)
        self.assertEqual(self.run_vault().returncode, 1)
        self.assertEqual(self.run_vault("get", "k", pw="bad").returncode, 2)
        self.run_vault("set", "x", "v", "--ttl", "0")
        self.assertEqual(self.run_vault("get", "x").returncode, 3)


if __name__ == "__main__":
    unittest.main()
