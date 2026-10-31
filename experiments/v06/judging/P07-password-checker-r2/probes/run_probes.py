"""Black-box probes. Same expectations for A and B; only invocation adapters differ."""
import json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# invocation adapters
def check_args(side, pw, pol):
    if side == "A":
        return ["check", pw, "-p", pol]
    return ["check", "--password", pw, "--policy", pol]
def gen_args(side, pol, length=None, count=None):
    a = ["generate", "-p" if side == "A" else "--policy", pol]
    if length is not None: a += ["--length", str(length)]
    if count is not None: a += ["--count", str(count)]
    return a
def val_args(side, pol):
    return ["validate-policy", pol] if side == "A" else ["validate-policy", "--policy", pol]

STRICT = {"min_length": 12, "require_uppercase": True, "require_lowercase": True,
          "require_digits": True, "require_symbols": True,
          "forbidden_passwords": ["password", "Tr0ub4dor&3x"]}
LOOSE = {"min_length": 4, "require_uppercase": False, "require_lowercase": False,
         "require_digits": False, "require_symbols": False, "forbidden_passwords": []}

def run(side, args, cwd, stdin=""):
    script = os.path.join(cwd, "password_checker.py")
    p = subprocess.run([sys.executable, "-I", script] + args, cwd=cwd, input=stdin,
                       capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr

def ent(out):
    m = re.search(r"([0-9]+\.[0-9]+)\s*bits", out)
    return float(m.group(1)) if m else None

def probes(side, d):
    def wpol(name, data, raw=None):
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write(raw if raw is not None else json.dumps(data))
        return path
    strict = wpol("strict.json", STRICT); loose = wpol("loose.json", LOOSE)
    R = {}
    nt = lambda e: "Traceback" not in e
    # P1 strong password passes, exit 0
    rc, o, e = run(side, check_args(side, "Xk9#mPq2$vLw", strict), d)
    R["P01_strong_passes"] = rc == 0 and nt(e)
    # P2 short only fails, exit nonzero, mentions length
    rc, o, e = run(side, check_args(side, "Ab1!x", strict), d)
    R["P02_min_length"] = rc != 0 and re.search(r"length|short", o + e, re.I) is not None
    # each class
    for pid, pw, word in [("P03_upper", "xk9#mpq2$vlw", "upper"), ("P04_lower", "XK9#MPQ2$VLW", "lower"),
                          ("P05_digit", "Xkz#mPqa$vLw", "digit"), ("P06_symbol", "Xk9zmPq2avLw", "symbol")]:
        rc, o, e = run(side, check_args(side, pw, strict), d)
        R[pid] = rc != 0 and word in (o + e).lower()
    # P7 forbidden (case-insensitive)
    rc, o, e = run(side, check_args(side, "PASSWORD", strict), d)
    R["P07_forbidden_ci"] = rc != 0 and "forbidden" in (o + e).lower()
    rc, o, e = run(side, check_args(side, "Tr0ub4dor&3x", strict), d)
    R["P08_forbidden_exact_otherwise_valid"] = rc != 0 and "forbidden" in (o + e).lower()
    # P9 every failure reported: "a" fails length, upper, digit, symbol (4 rules)
    rc, o, e = run(side, check_args(side, "a", strict), d)
    lo = (o + e).lower()
    R["P09_reports_all_failures"] = rc != 0 and all(w in lo for w in ["upper", "digit", "symbol"]) and re.search(r"length|short", lo) is not None
    # P10 configurable: loose policy accepts "abcd"
    rc, o, e = run(side, check_args(side, "abcd", loose), d)
    R["P10_configurable_loose"] = rc == 0
    # entropy
    rc, o, e = run(side, check_args(side, "abcd", loose), d)
    R["P11_entropy_abcd_8"] = ent(o) is not None and abs(ent(o) - 8.0) < 0.01
    rc, o, e = run(side, check_args(side, "aaaa", loose), d)
    R["P12_entropy_aaaa_0"] = ent(o) is not None and abs(ent(o)) < 0.01
    rc, o, e = run(side, check_args(side, "aabb", loose), d)
    R["P13_entropy_aabb_4"] = ent(o) is not None and abs(ent(o) - 4.0) < 0.01
    # generate
    rc, o, e = run(side, gen_args(side, strict, count=20), d)
    pws = [l.split("\t")[0] for l in o.splitlines() if l.strip()]
    ok = rc == 0 and len(pws) == 20 and len(set(pws)) == 20
    for pw in pws:
        rc2, _, _ = run(side, check_args(side, pw, strict), d)
        ok = ok and rc2 == 0
    R["P14_generate_satisfies_policy"] = ok
    rc, o, e = run(side, gen_args(side, strict, length=30), d)
    R["P15_generate_length"] = rc == 0 and len(o.strip()) == 30
    # P16 generate below min_length must not silently produce wrong length
    rc, o, e = run(side, gen_args(side, strict, length=5), d)
    R["P16_generate_short_length_not_silent"] = nt(e) and (rc != 0 or len(o.strip()) == 5)
    # validate-policy
    rc, o, e = run(side, val_args(side, strict), d)
    R["P17_validate_good"] = rc == 0 and nt(e)
    bad = wpol("bad.json", {"min_length": "x", "require_uppercase": "yes"})
    rc, o, e = run(side, val_args(side, bad), d)
    R["P18_validate_bad_types"] = rc != 0 and nt(e) and "min_length" in (o + e)
    badj = wpol("badj.json", None, raw="{not json")
    rc, o, e = run(side, val_args(side, badj), d)
    R["P19_validate_bad_json"] = rc != 0 and nt(e)
    rc, o, e = run(side, val_args(side, os.path.join(d, "nope.json")), d)
    R["P20_validate_missing_file"] = rc != 0 and nt(e)
    neg = wpol("neg.json", {"min_length": -1})
    rc, o, e = run(side, val_args(side, neg), d)
    R["P21_validate_negative_len"] = rc != 0 and nt(e)
    # P22 check with invalid policy file: graceful error
    rc, o, e = run(side, check_args(side, "whatever", badj), d)
    R["P22_check_bad_policy_graceful"] = rc != 0 and nt(e)
    # P23 policy.json in cwd is used by default by validate-policy
    shutil.copy(strict, os.path.join(d, "policy.json"))
    args = ["validate-policy"]
    rc, o, e = run(side, args, d)
    R["P23_validate_default_policy_json"] = rc == 0 and "policy.json" in (o + e)
    # P24 stdin password input works
    a = ["check", "-p", strict] if side == "A" else ["check", "--policy", strict]
    rc, o, e = run(side, a, d, stdin="Xk9#mPq2$vLw\n")
    R["P24_check_stdin"] = rc == 0
    # P25 stdlib only
    src = open(os.path.join(d, "password_checker.py")).read()
    mods = set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_]+)", src, re.M))
    R["P25_stdlib_only"] = mods <= set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else all(m in {"argparse","json","math","secrets","string","sys","collections","getpass","os","re"} for m in mods)
    # P26 secure RNG (no `random` module)
    R["P26_uses_secrets"] = "secrets" in mods and "random" not in mods
    # P27 generate with all classes off still works & satisfies
    rc, o, e = run(side, gen_args(side, loose), d)
    R["P27_generate_loose"] = rc == 0 and len(o.strip()) >= 4
    # P28 check without policy flag uses policy.json from cwd
    shutil.copy(loose, os.path.join(d, "policy.json"))
    a = ["check", "abcd"] if side == "A" else ["check", "--password", "abcd"]
    rc, o, e = run(side, a, d)
    R["P28_check_uses_cwd_policy_json"] = rc == 0
    return {k: ("pass" if v else "fail") for k, v in R.items()}

results = {}
for side in ("A", "B"):
    with tempfile.TemporaryDirectory() as d:
        shutil.copy(os.path.join(ROOT, side, "password_checker.py"), d)
        results[side] = probes(side, d)
with open(os.path.join(ROOT, "probes", "results.json"), "w") as f:
    json.dump(results, f, indent=2)
for k in results["A"]:
    print(f"{k:42} A={results['A'][k]:5} B={results['B'][k]}")
