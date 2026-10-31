"""P25: 8 concurrent `set` with distinct keys must all persist (no lost updates)."""
import os, subprocess, sys, tempfile, site, json
V = os.path.abspath(sys.argv[1]); h = tempfile.mkdtemp()
env = {"PATH": os.environ["PATH"], "HOME": h, "PYTHONUSERBASE": site.getuserbase(), "VAULT_MASTER_KEY": "pw"}
subprocess.run([sys.executable, V, "set", "seed", "v"], env=env, capture_output=True)
ps = [subprocess.Popen([sys.executable, V, "set", "k%d" % i, "v"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(8)]
[p.wait() for p in ps]
out = subprocess.run([sys.executable, V, "list"], env=env, capture_output=True, text=True).stdout
n = sum(1 for i in range(8) if out.startswith("k%d\t" % i) or "\nk%d\t" % i in out)
print(json.dumps({"P25_concurrent_sets_no_lost_update": "pass" if n == 8 else "fail", "persisted": n}))
