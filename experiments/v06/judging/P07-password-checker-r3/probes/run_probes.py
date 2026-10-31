import json, os, subprocess, sys, tempfile, math, ast, string
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRICT = {"min_length": 10, "require_uppercase": True, "require_lowercase": True,
          "require_digits": True, "require_symbols": True,
          "forbidden_passwords": ["Summer2024!x"]}

def run(side, args, cwd, stdin=""):
    prog = os.path.join(ROOT, side, "password_checker.py")
    p = subprocess.run([sys.executable, prog] + args, cwd=cwd, input=stdin,
                       capture_output=True, text=True, timeout=20)
    return p.returncode, p.stdout, p.stderr

def vp(side, path):  # adapt validate-policy invocation only
    return ["validate-policy", "--policy", path] if side == "A" else ["validate-policy", path]

def wpol(d, pol, name="p.json"):
    path = os.path.join(d, name)
    with open(path, "w") as f:
        f.write(pol if isinstance(pol, str) else json.dumps(pol))
    return path

def probes(side):
    r = {}
    d = tempfile.mkdtemp()
    P = wpol(d, STRICT)
    def chk(pw, pol=P):
        return run(side, ["check", pw, "--policy", pol], d)
    def tc(name, fn):
        try: r[name] = "pass" if fn() else "fail"
        except Exception as e: r[name] = "fail"; print(side, name, "EXC", e)
    # R3-R8
    tc("P01_short_fails", lambda: (lambda c: c[0] != 0 and "PASS" not in c[1].upper().split("\n")[0] )(chk("Ab1!xyz")))
    tc("P02_no_upper_fails", lambda: chk("abcdefgh1!x")[0] != 0)
    tc("P03_no_lower_fails", lambda: chk("ABCDEFGH1!X")[0] != 0)
    tc("P04_no_digit_fails", lambda: chk("Abcdefghi!x")[0] != 0)
    tc("P05_no_symbol_fails", lambda: chk("Abcdefghi1x")[0] != 0)
    tc("P06_forbidden_fails", lambda: chk("Summer2024!x")[0] != 0)
    tc("P07_forbidden_case_insensitive", lambda: chk("summer2024!X")[0] != 0)
    tc("P08_good_passes", lambda: chk("Abcdefgh1!xy")[0] == 0)
    # R9 every failed rule: "aaaa" fails short, upper, digit, symbol -> 4 bullet lines
    def p09():
        c, o, e = chk("aaaa")
        return c != 0 and sum(1 for l in o.splitlines() if l.strip().startswith("- ")) == 4
    tc("P09_reports_all_failures", p09)
    # R10 entropy: "aabb" -> 4.00 bits total; "abcd" -> 8.00
    def p10():
        o1 = chk("aabb")[1]; o2 = chk("Abcdefgh1!xy")[1]
        exp2 = 12 * -sum((c/12)*math.log2(c/12) for c in [1]*12)
        return "4.00" in o1 and ("%.2f" % exp2) in o2 and "bits" in o2
    tc("P10_entropy_bits", p10)
    # R11 configurable: disable symbol requirement, min 4
    def p11():
        pol = wpol(d, {"min_length": 4, "require_uppercase": False, "require_lowercase": True,
                       "require_digits": False, "require_symbols": False, "forbidden_passwords": []}, "loose.json")
        return chk("abcd", pol)[0] == 0 and chk("abc", pol)[0] != 0
    tc("P11_configurable_policy", p11)
    # R12 default policy.json in cwd
    def p12():
        d2 = tempfile.mkdtemp()
        wpol(d2, {"min_length": 3, "require_uppercase": False, "require_lowercase": False,
                  "require_digits": False, "require_symbols": False, "forbidden_passwords": []}, "policy.json")
        return run(side, ["check", "xyz"], d2)[0] == 0
    tc("P12_policy_json_autoload", p12)
    # R13 generate satisfies policy
    def p13():
        c, o, e = run(side, ["generate", "--policy", P, "--count", "20"], d)
        pws = [l for l in o.splitlines() if l.strip()]
        if c != 0 or len(pws) != 20: return False
        for pw in pws:
            if len(pw) < 10 or not any(x.isupper() for x in pw) or not any(x.islower() for x in pw) \
               or not any(x.isdigit() for x in pw) or not any(x in string.punctuation for x in pw):
                return False
            if chk(pw)[0] != 0: return False
        return len(set(pws)) == 20
    tc("P13_generate_satisfies_policy", p13)
    def p13b():
        c, o, e = run(side, ["generate", "--policy", P, "--length", "30"], d)
        return c == 0 and len(o.strip()) == 30
    tc("P14_generate_length", p13b)
    def p13c():  # length below min_length must not produce noncompliant output silently
        c, o, e = run(side, ["generate", "--policy", P, "--length", "5"], d)
        return c != 0 and "Traceback" not in e
    tc("P15_generate_too_short_rejected", p13c)
    # R14 secrets
    def p14():
        src = open(os.path.join(ROOT, side, "password_checker.py")).read()
        return "secrets" in src and "import random" not in src
    tc("P16_csprng", p14)
    # R2 stdlib only
    def p2():
        tree = ast.parse(open(os.path.join(ROOT, side, "password_checker.py")).read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
            if isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
        return mods <= set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else \
            mods <= {"argparse","json","math","secrets","string","sys","collections","getpass","os"}
    tc("P17_stdlib_only", p2)
    # R15 validate-policy
    tc("P18_validate_good", lambda: run(side, vp(side, P), d)[0] == 0)
    def bad(pol, nm):
        c, o, e = run(side, vp(side, wpol(d, pol, nm)), d)
        return c != 0 and "Traceback" not in e
    tc("P19_validate_bad_type", lambda: bad({**STRICT, "min_length": "ten"}, "b1.json"))
    tc("P20_validate_negative_len", lambda: bad({**STRICT, "min_length": -3}, "b2.json"))
    tc("P21_validate_bad_bool", lambda: bad({**STRICT, "require_digits": "yes"}, "b3.json"))
    tc("P22_validate_unknown_key", lambda: bad({**STRICT, "min_lenght": 5}, "b4.json"))
    tc("P23_validate_malformed_json", lambda: bad("{not json", "b5.json"))
    tc("P24_validate_not_object", lambda: bad("[1,2]", "b6.json"))
    tc("P25_validate_forbidden_not_list", lambda: bad({**STRICT, "forbidden_passwords": "abc"}, "b7.json"))
    tc("P26_validate_missing_file", lambda: (lambda c: c[0] != 0 and "Traceback" not in c[2])(run(side, vp(side, os.path.join(d, "nope.json")), d)))
    # R17 check with missing/bad policy
    tc("P27_check_missing_policy", lambda: (lambda c: c[0] != 0 and "Traceback" not in c[2])(chk("Abcdefgh1!xy", os.path.join(d, "nope.json"))))
    tc("P28_check_invalid_policy", lambda: (lambda c: c[0] != 0 and "Traceback" not in c[2])(chk("Abcdefgh1!xy", wpol(d, {**STRICT, "min_length": "x"}, "b8.json"))))
    # stdin password
    tc("P29_check_stdin", lambda: run(side, ["check", "--policy", P], d, stdin="Abcdefgh1!xy\n")[0] == 0)
    # generate with no class requirements
    def p30():
        pol = wpol(d, {"min_length": 8, "require_uppercase": False, "require_lowercase": False,
                       "require_digits": False, "require_symbols": False, "forbidden_passwords": []}, "none.json")
        c, o, e = run(side, ["generate", "--policy", pol], d)
        return c == 0 and len(o.strip()) >= 8
    tc("P30_generate_no_classes", p30)
    # empty password: entropy 0 and fails
    tc("P31_empty_password", lambda: (lambda c: c[0] == 1 and "Traceback" not in c[2])(chk("")))
    # generate count 0 / negative should not silently succeed with nothing
    tc("P32_generate_bad_count", lambda: (lambda c: c[0] != 0 and "Traceback" not in c[2])(run(side, ["generate", "--policy", P, "--count", "0"], d)))
    # Unicode uppercase counted
    tc("P33_unicode_upper_symbol", lambda: chk("Ébcdefgh1!xy".replace("A","")) [0] == 0)
    return r

res = {s: probes(s) for s in ("A", "B")}
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
for s in res:
    print(s, sum(v == "pass" for v in res[s].values()), "/", len(res[s]), [k for k, v in res[s].items() if v == "fail"])
