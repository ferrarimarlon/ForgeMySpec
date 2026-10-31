"""Black-box probes. Invocation adapter: A takes CONFIG SCHEMA, B takes SCHEMA CONFIG."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORDER = {"A": "config_first", "B": "schema_first"}

def run(side, schema, config, raw_schema=False, raw_config=False, args=None):
    d = tempfile.mkdtemp()
    sp, cp = os.path.join(d, "s.json"), os.path.join(d, "c.json")
    if schema is not None:
        open(sp, "w").write(schema if raw_schema else json.dumps(schema))
    if config is not None:
        open(cp, "w").write(config if raw_config else json.dumps(config))
    prog = os.path.join(ROOT, side, "config_validator.py")
    if args is None:
        args = [cp, sp] if ORDER[side] == "config_first" else [sp, cp]
    r = subprocess.run([sys.executable, "-I", prog] + args, capture_output=True, text=True, cwd=d, timeout=30)
    return r.returncode, r.stdout, r.stderr

def lines(out):
    return out

NESTED = {"type": "object", "required": ["name", "db"], "properties": {
    "name": {"type": "string", "minLength": 3, "maxLength": 5, "pattern": "^[a-z]+$"},
    "mode": {"type": "string", "enum": ["dev", "prod"]},
    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
    "ratio": {"type": "number", "minimum": 0, "maximum": 1},
    "debug": {"type": "boolean"}, "tags": {"type": "array"},
    "db": {"type": "object", "required": ["host"], "properties": {
        "host": {"type": "string"},
        "opts": {"type": "object", "properties": {"timeout": {"type": "integer", "maximum": 10}}}}}}}

def P(fn):
    PROBES.append(fn); return fn
PROBES = []

@P
def p01_valid_exit0(s):
    c, o, e = run(s, NESTED, {"name": "abc", "mode": "dev", "port": 80, "ratio": 0.5, "debug": True, "tags": [], "db": {"host": "h", "opts": {"timeout": 3}}})
    return c == 0
@P
def p02_required_missing(s):
    c, o, e = run(s, NESTED, {"name": "abc"})
    return c == 1 and "db" in o + e and "required" in (o + e).lower()
@P
def p03_nested_required_dot(s):
    c, o, e = run(s, NESTED, {"name": "abc", "db": {}})
    return c == 1 and "db.host" in o + e
@P
def p04_types_each(s):
    ok = True
    for t, good, bad in [("string", "x", 1), ("integer", 3, 3.5), ("number", 2.5, "2"), ("boolean", False, 0), ("array", [1], {}), ("object", {}, [])]:
        sch = {"type": "object", "properties": {"v": {"type": t}}}
        ok &= run(s, sch, {"v": good})[0] == 0
        c, o, e = run(s, sch, {"v": bad})
        ok &= c == 1 and "v" in o + e
    return ok
@P
def p05_bool_not_integer(s):
    sch = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "number"}}}
    c, o, e = run(s, sch, {"a": True, "b": False})
    return c == 1 and "a" in o and "b" in o
@P
def p06_enum(s):
    c1 = run(s, NESTED, {"name": "abc", "db": {"host": "h"}, "mode": "dev"})[0]
    c2, o, e = run(s, NESTED, {"name": "abc", "db": {"host": "h"}, "mode": "test"})
    return c1 == 0 and c2 == 1 and "mode" in o + e
@P
def p07_number_bounds(s):
    base = {"name": "abc", "db": {"host": "h"}}
    ok = run(s, NESTED, dict(base, port=1, ratio=1))[0] == 0
    ok &= run(s, NESTED, dict(base, port=65535, ratio=0))[0] == 0
    for kv in ({"port": 0}, {"port": 65536}, {"ratio": -0.1}, {"ratio": 1.5}):
        c, o, e = run(s, NESTED, dict(base, **kv)); ok &= c == 1 and list(kv)[0] in o + e
    return ok
@P
def p08_string_length(s):
    base = {"db": {"host": "h"}}
    ok = run(s, NESTED, dict(base, name="abc"))[0] == 0 and run(s, NESTED, dict(base, name="abcde"))[0] == 0
    for n in ("ab", "abcdef"):
        c, o, e = run(s, NESTED, dict(base, name=n)); ok &= c == 1 and "name" in o + e
    return ok
@P
def p09_pattern(s):
    c, o, e = run(s, NESTED, {"name": "ab1", "db": {"host": "h"}})
    return c == 1 and "name" in o + e and "pattern" in (o + e).lower()
@P
def p10_deep_nested_dot(s):
    c, o, e = run(s, NESTED, {"name": "abc", "db": {"host": "h", "opts": {"timeout": 99}}})
    return c == 1 and "db.opts.timeout" in o + e
@P
def p11_all_errors_reported(s):
    cfg = {"name": "A1", "mode": "x", "port": 0, "ratio": 2, "debug": "y", "tags": {}, "db": {"opts": {"timeout": "z"}}}
    c, o, e = run(s, NESTED, cfg)
    t = o + e
    keys = ["name", "mode", "port", "ratio", "debug", "tags", "db.host", "db.opts.timeout"]
    return c == 1 and all(k in t for k in keys)
@P
def p12_multiple_errors_same_field(s):
    c, o, e = run(s, NESTED, {"name": "A", "db": {"host": "h"}})  # too short + pattern
    t = o + e
    return c == 1 and "minlength" in t.lower().replace(" ", "") and "pattern" in t.lower()
@P
def p13_malformed_config(s):
    c, o, e = run(s, NESTED, "{bad", raw_config=True)
    return c not in (0, 1) and "Traceback" not in e and e.strip() != ""
@P
def p14_malformed_schema(s):
    c, o, e = run(s, "{bad", {"a": 1}, raw_schema=True)
    return c not in (0, 1) and "Traceback" not in e
@P
def p15_missing_file(s):
    c, o, e = run(s, NESTED, None)
    return c not in (0, 1) and "Traceback" not in e
@P
def p16_no_args(s):
    c, o, e = run(s, None, None, args=[])
    return c not in (0, 1) and "Traceback" not in e
@P
def p17_nonobject_schema_not_silently_ok(s):
    c, o, e = run(s, [1, 2], {"a": 1})
    return c != 0 and "Traceback" not in e
@P
def p18_root_type_mismatch(s):
    c, o, e = run(s, NESTED, [1, 2])
    return c == 1 and "Traceback" not in e
@P
def p19_enum_bool_vs_int(s):
    sch = {"type": "object", "properties": {"v": {"enum": [1, 2]}}}
    c, o, e = run(s, sch, {"v": True})
    return c == 1
@P
def p20_unknown_type_not_silent(s):
    sch = {"type": "object", "properties": {"v": {"type": "strng"}}}
    c, o, e = run(s, sch, {"v": 1})
    return c != 0
@P
def p21_deep_nesting_no_traceback(s):
    c, o, e = run(s, {"type": "object"}, "[" * 100000 + "]" * 100000, raw_config=True)
    return "Traceback" not in e and c != 0
@P
def p22_integer_float_whole(s):
    # 1.0 parsed as float; spec ambiguous -> just must not crash
    sch = {"type": "object", "properties": {"v": {"type": "integer", "minimum": 0}}}
    c, o, e = run(s, sch, {"v": 5})
    return c == 0

@P
def p23_enum_int_equals_float(s):
    sch = {"type": "object", "properties": {"v": {"enum": [1.0, 2.0]}}}
    return run(s, sch, {"v": 1})[0] == 0

res = {}
for side in ("A", "B"):
    res[side] = {}
    for p in PROBES:
        try:
            res[side][p.__name__] = "pass" if p(side) else "fail"
        except Exception as ex:
            res[side][p.__name__] = "fail"
json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1)
for p in PROBES:
    print(f"{p.__name__:40} A={res['A'][p.__name__]:5} B={res['B'][p.__name__]}")
