"""Black-box probes. Usage: python3 run_probes.py <side_dir>  -> prints JSON {probe: pass|fail}"""
import json, os, subprocess, sys, tempfile, re, ast
side = os.path.abspath(sys.argv[1])
prog = os.path.join(side, "password_checker.py")
res = {}
def run(args, cwd, stdin=None):
    return subprocess.run([sys.executable, "-I", prog] + args, cwd=cwd, input=stdin,
                          capture_output=True, text=True, timeout=30)
def probe(pid, fn):
    if not os.path.isfile(prog):
        res[pid] = "fail"; return
    try:
        res[pid] = "pass" if fn() else "fail"
    except Exception as e:
        res[pid] = "fail"
def write(d, obj, name="policy.json"):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return p
FULL = {"min_length": 12, "require_uppercase": True, "require_lowercase": True,
        "require_digits": True, "require_symbols": True, "forbidden_passwords": ["password", "letmein"]}
def chk(pw, pol, d, extra=()):
    p = write(d, pol)
    return run(["check", pw, "-p", p, *extra], d)
with tempfile.TemporaryDirectory() as d:
    probe("P01_single_file_exists", lambda: os.path.isfile(prog))
    def stdlib():
        tree = ast.parse(open(prog).read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            if isinstance(n, ast.ImportFrom) and n.module: mods.add(n.module.split(".")[0])
        import importlib.util, sysconfig
        std = sysconfig.get_paths()["stdlib"]
        def is_std(m):
            if m in sys.builtin_module_names: return True
            sp = importlib.util.find_spec(m)
            return sp is not None and (sp.origin in ("built-in","frozen") or (sp.origin or "").startswith(std)) and "site-packages" not in (sp.origin or "")
        return all(is_std(m) for m in mods)
    probe("P02_stdlib_only", stdlib)
    probe("P03_check_strong_passes", lambda: chk("Xk9#mPq2$vLw7!", FULL, d).returncode == 0)
    probe("P04_min_length_fail", lambda: (lambda r: r.returncode != 0 and re.search(r"short|length", r.stdout + r.stderr, re.I))(chk("Ab1!x", FULL, d)))
    probe("P05_min_length_configurable", lambda: chk("Ab1!xyz", dict(FULL, min_length=6), d).returncode == 0)
    probe("P06_uppercase_fail", lambda: (lambda r: r.returncode != 0 and re.search(r"upper", r.stdout+r.stderr, re.I))(chk("xk9#mpq2$vlw7!", FULL, d)))
    probe("P07_lowercase_fail", lambda: (lambda r: r.returncode != 0 and re.search(r"lower", r.stdout+r.stderr, re.I))(chk("XK9#MPQ2$VLW7!", FULL, d)))
    probe("P08_digit_fail", lambda: (lambda r: r.returncode != 0 and re.search(r"digit|number", r.stdout+r.stderr, re.I))(chk("Xkz#mPqa$vLwb!", FULL, d)))
    probe("P09_symbol_fail", lambda: (lambda r: r.returncode != 0 and re.search(r"symbol|special", r.stdout+r.stderr, re.I))(chk("Xk9zmPq2avLw7b", FULL, d)))
    probe("P10_class_rules_configurable_off", lambda: chk("abcdefghijkq", dict(FULL, require_uppercase=False, require_digits=False, require_symbols=False), d).returncode == 0)
    probe("P11_forbidden_common_fail", lambda: (lambda r: r.returncode != 0 and re.search(r"forbid|common", r.stdout+r.stderr, re.I))(chk("letmein", dict(FULL, min_length=1, require_uppercase=False, require_digits=False, require_symbols=False), d)))
    probe("P12_forbidden_list_configurable", lambda: chk("zebrazebra", dict(FULL, min_length=1, require_uppercase=False, require_digits=False, require_symbols=False, forbidden_passwords=["zebrazebra"]), d).returncode != 0)
    def all_failures():
        r = chk("abc", FULL, d)
        o = (r.stdout + r.stderr).lower()
        return r.returncode != 0 and all(k in o for k in ["short", "upper", "digit", "symbol"])
    probe("P13_reports_every_failed_rule", all_failures)
    def entropy():
        r = chk("aabb", dict(FULL, min_length=1), d)
        o = r.stdout + r.stderr
        # Shannon: per-char 1 bit; total 4 bits. accept 1.0 or 4.0
        return re.search(r"bit", o, re.I) and re.search(r"\b(4(\.0+)?|1(\.0+)?)\b", o)
    probe("P14_shannon_entropy_aabb", entropy)
    def entropy2():
        r = chk("abcd", dict(FULL, min_length=1), d)
        o = r.stdout + r.stderr
        return re.search(r"\b(8(\.0+)?|2(\.0+)?)\b", o) and "bit" in o.lower()
    probe("P15_shannon_entropy_abcd", entropy2)
    def gen_ok():
        p = write(d, FULL)
        r = run(["generate", "-p", p, "-n", "5"], d)
        pws = [l.split()[0] for l in r.stdout.splitlines() if l.strip()]
        if r.returncode != 0 or len(pws) < 1: return False
        for pw in pws:
            if run(["check", pw, "-p", p], d).returncode != 0: return False
        return len(set(pws)) == len(pws)
    probe("P16_generate_satisfies_policy", gen_ok)
    def gen_csprng():
        return "secrets" in open(prog).read() or "SystemRandom" in open(prog).read()
    probe("P17_generate_uses_csprng", gen_csprng)
    def gen_respects_length():
        p = write(d, dict(FULL, min_length=20))
        r = run(["generate", "-p", p], d)
        pw = r.stdout.split()[0]
        return r.returncode == 0 and len(pw) >= 20
    probe("P18_generate_respects_min_length", gen_respects_length)
    def cwd_policy():
        with tempfile.TemporaryDirectory() as d2:
            write(d2, dict(FULL, min_length=30))
            r = run(["check", "Xk9#mPq2$vLw7!"], d2)
            return r.returncode != 0
    probe("P19_check_loads_policy_json_from_cwd_by_default", cwd_policy)
    def vp_ok():
        p = write(d, FULL)
        return run(["validate-policy", p], d).returncode == 0
    probe("P20_validate_policy_valid", vp_ok)
    def vp_badtype():
        p = write(d, dict(FULL, min_length="twelve"), "bad.json")
        r = run(["validate-policy", p], d)
        return r.returncode != 0 and "Traceback" not in r.stderr
    probe("P21_validate_policy_bad_type", vp_badtype)
    def vp_badjson():
        p = write(d, "{not json", "bad2.json")
        r = run(["validate-policy", p], d)
        return r.returncode != 0 and "Traceback" not in r.stderr
    probe("P22_validate_policy_malformed_json", vp_badjson)
    def vp_neg():
        p = write(d, dict(FULL, min_length=-3), "bad3.json")
        r = run(["validate-policy", p], d)
        return r.returncode != 0
    probe("P23_validate_policy_negative_length", vp_neg)
    def missing_file():
        r = run(["check", "abc", "-p", os.path.join(d, "nope.json")], d)
        return r.returncode != 0 and "Traceback" not in r.stderr
    probe("P24_missing_policy_file_graceful", missing_file)
    def gen_entropy_policy():
        p = write(d, dict(FULL, min_entropy=70))
        r = run(["generate", "-p", p], d)
        return r.returncode == 0 and "Traceback" not in r.stderr
    probe("P25_generate_high_min_entropy_policy", gen_entropy_policy)
    def check_stdin():
        p = write(d, FULL)
        r = run(["check", "-p", p], d, stdin="Xk9#mPq2$vLw7!\n")
        return r.returncode == 0
    probe("P26_check_reads_stdin", check_stdin)
    probe("P27_help_lists_subcommands", lambda: all(s in run(["--help"], d).stdout for s in ["check", "generate", "validate-policy"]))
print(json.dumps(res, indent=1))
