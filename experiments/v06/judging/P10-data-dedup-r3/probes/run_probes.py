import json, os, subprocess, sys, tempfile, csv, ast
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = "id,region,val\n1,eu,a\n2,eu,b\n1,us,c\n1,eu,d\n2,eu,e\n"

def run(side, inp, out, key, strategy=None):
    prog = os.path.join(ROOT, side, "data_dedup.py")
    if side == "A":
        cmd = [sys.executable, "-I", prog, inp, out, "-k", key]
    else:
        cmd = [sys.executable, "-I", prog, inp, "-k", key, "-o", out]
    if strategy: cmd += ["-s", strategy]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

def rows(p):
    with open(p, newline="") as f: return list(csv.reader(f))

def setup(d, content=SAMPLE, name="in.csv"):
    p = os.path.join(d, name)
    with open(p, "w", newline="") as f: f.write(content)
    return p, os.path.join(d, "out.csv")

def P1(side, d):  # single file, stdlib only
    files = [f for f in os.listdir(os.path.join(ROOT, side)) if f.endswith(".py")]
    tree = ast.parse(open(os.path.join(ROOT, side, "data_dedup.py")).read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    return "data_dedup.py" in files and mods <= {"argparse","csv","sys","os","io","re","collections","itertools","pathlib","typing","dataclasses","json","functools"}

def P2(side, d):  # single key first default
    i, o = setup(d); r = run(side, i, o, "id")
    return r.returncode == 0 and rows(o) == [["id","region","val"],["1","eu","a"],["2","eu","b"]]

def P3(side, d):  # composite key first
    i, o = setup(d); r = run(side, i, o, "id,region", "first")
    return r.returncode == 0 and rows(o) == [["id","region","val"],["1","eu","a"],["2","eu","b"],["1","us","c"]]

def P4(side, d):  # keep last: kept rows are the last occurrences
    i, o = setup(d); r = run(side, i, o, "id,region", "last")
    if r.returncode != 0: return False
    got = rows(o)
    return got[0] == ["id","region","val"] and sorted(map(tuple, got[1:])) == sorted([("1","us","c"),("1","eu","d"),("2","eu","e")])

def P5(side, d):  # error strategy nonzero + reports duplicate key
    i, o = setup(d); r = run(side, i, o, "id,region", "error")
    return r.returncode != 0 and "eu" in (r.stdout + r.stderr) and "1" in (r.stdout + r.stderr)

def P6(side, d):  # error strategy with no dups -> exit 0, output written
    i, o = setup(d); r = run(side, i, o, "id,region,val", "error")
    return r.returncode == 0 and len(rows(o)) == 6

def P7(side, d):  # summary includes counts found=2 removed=2
    i, o = setup(d); r = run(side, i, o, "id,region")
    s = (r.stdout + r.stderr).lower()
    return r.returncode == 0 and "duplicate" in s and "2" in s and "removed" in s

def P8(side, d):  # summary correct with zero dups
    i, o = setup(d); r = run(side, i, o, "val")
    s = (r.stdout + r.stderr).lower()
    return r.returncode == 0 and "0" in s and "removed" in s

def P9(side, d):  # missing key column -> nonzero, no traceback
    i, o = setup(d); r = run(side, i, o, "nope")
    return r.returncode != 0 and "Traceback" not in r.stderr and "nope" in r.stderr

def P10(side, d):  # missing input file -> nonzero, no traceback
    r = run(side, os.path.join(d, "nofile.csv"), os.path.join(d, "o.csv"), "id")
    return r.returncode != 0 and "Traceback" not in r.stderr

def P11(side, d):  # quoted fields with commas/newlines preserved
    c = 'id,text\n1,"a, b"\n1,"x\ny"\n2,"q ""z"""\n'
    i, o = setup(d, c); r = run(side, i, o, "id")
    return r.returncode == 0 and rows(o) == [["id","text"],["1","a, b"],["2",'q "z"']]

def P12(side, d):  # empty input file -> nonzero clean error
    i, o = setup(d, ""); r = run(side, i, o, "id")
    return r.returncode != 0 and "Traceback" not in r.stderr

def P13(side, d):  # header-only file -> exit 0, output has header
    i, o = setup(d, "id,v\n"); r = run(side, i, o, "id")
    return r.returncode == 0 and rows(o) == [["id","v"]]

def P14(side, d):  # error strategy writes no output file
    i, o = setup(d); r = run(side, i, o, "id", "error")
    return r.returncode != 0 and not os.path.exists(o)

def P15(side, d):  # composite key does not falsely merge on concatenation ("1","12") vs ("11","2")
    c = "a,b\n1,12\n11,2\n"
    i, o = setup(d, c); r = run(side, i, o, "a,b")
    return r.returncode == 0 and len(rows(o)) == 3

def P16(side, d):  # non-UTF8 input -> clean error
    p = os.path.join(d, "in.csv")
    open(p, "wb").write(b"id,v\n1,\xff\xfe\n")
    r = run(side, p, os.path.join(d, "out.csv"), "id")
    return "Traceback" not in r.stderr

def P17(side, d):  # short row (missing key column value) -> no traceback
    c = "id,region,val\n1,eu,a\n2\n"
    i, o = setup(d, c); r = run(side, i, o, "region")
    return "Traceback" not in r.stderr

def P18(side, d):  # unwritable output path -> clean error
    i, _ = setup(d); r = run(side, i, os.path.join(d, "nodir", "out.csv"), "id")
    return r.returncode != 0 and "Traceback" not in r.stderr

probes = [P1,P2,P3,P4,P5,P6,P7,P8,P9,P10,P11,P12,P13,P14,P15,P16,P17,P18]
res = {}
for side in ("A", "B"):
    res[side] = {}
    for p in probes:
        with tempfile.TemporaryDirectory() as d:
            try: ok = p(side, d)
            except Exception as e: ok = False; print(side, p.__name__, "EXC", e)
        res[side][p.__name__] = "pass" if ok else "fail"
json.dump(res, open(os.path.join(ROOT, "probes", "results.json"), "w"), indent=1)
print(json.dumps(res))
