"""Black-box probes. Usage: python3 -I run_probes.py <side_dir> -> prints JSON {probe: pass|fail}"""
import json, os, subprocess, sys, tempfile

side = os.path.abspath(sys.argv[1])
script = os.path.join(side, "config_validator.py")
results, details = {}, {}

def run(config, schema, raw_config=False, raw_schema=False, args=None):
    d = tempfile.mkdtemp()
    cp, sp = os.path.join(d, "c.json"), os.path.join(d, "s.json")
    with open(cp, "w") as f: f.write(config if raw_config else json.dumps(config))
    with open(sp, "w") as f: f.write(schema if raw_schema else json.dumps(schema))
    a = args if args is not None else [cp, sp]
    p = subprocess.run([sys.executable, script] + a, capture_output=True, text=True, cwd=d, timeout=30)
    return p.returncode, p.stdout + p.stderr

def probe(pid, fn):
    try:
        ok, info = fn()
    except Exception as e:
        ok, info = False, repr(e)
    results[pid] = "pass" if ok else "fail"
    details[pid] = info

S = {"type": "object", "required": ["name", "port"], "properties": {
    "name": {"type": "string", "minLength": 2, "maxLength": 10, "pattern": "^[a-z]+$"},
    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
    "ratio": {"type": "number", "minimum": 0, "maximum": 1},
    "debug": {"type": "boolean"},
    "tags": {"type": "array"},
    "mode": {"type": "string", "enum": ["dev", "prod"]},
    "server": {"type": "object", "required": ["host"], "properties": {
        "host": {"type": "string"},
        "tls": {"type": "object", "required": ["cert"], "properties": {"cert": {"type": "string"}, "level": {"type": "integer", "maximum": 3}}}}}}}
VALID = {"name": "app", "port": 80, "ratio": 0.5, "debug": True, "tags": [], "mode": "dev",
         "server": {"host": "h", "tls": {"cert": "c", "level": 1}}}

def p_valid():
    rc, out = run(VALID, S); return rc == 0, (rc, out)
def p_required():
    rc, out = run({"name": "app"}, S); return rc != 0 and "port" in out, (rc, out)
def type_probe(field, bad):
    def f():
        c = dict(VALID); c[field] = bad
        rc, out = run(c, S); return rc != 0 and field in out, (rc, out)
    return f
def p_bool_not_int():
    c = dict(VALID); c["port"] = True
    rc, out = run(c, S); return rc != 0 and "port" in out, (rc, out)
def p_int_accepts_number_ok():
    c = dict(VALID); c["ratio"] = 1
    rc, out = run(c, S); return rc == 0, (rc, out)
def p_float_not_int():
    c = dict(VALID); c["port"] = 80.5
    rc, out = run(c, S); return rc != 0 and "port" in out, (rc, out)
def p_enum():
    c = dict(VALID); c["mode"] = "test"
    rc, out = run(c, S); return rc != 0 and "mode" in out, (rc, out)
def p_min():
    c = dict(VALID); c["port"] = 0
    rc, out = run(c, S); return rc != 0 and "port" in out, (rc, out)
def p_max():
    c = dict(VALID); c["port"] = 70000
    rc, out = run(c, S); return rc != 0 and "port" in out, (rc, out)
def p_num_min():
    c = dict(VALID); c["ratio"] = -0.1
    rc, out = run(c, S); return rc != 0 and "ratio" in out, (rc, out)
def p_boundary():
    c = dict(VALID); c["port"] = 65535; c["ratio"] = 0; c["name"] = "ab"
    rc, out = run(c, S); return rc == 0, (rc, out)
def p_minlen():
    c = dict(VALID); c["name"] = "a"
    rc, out = run(c, S); return rc != 0 and "name" in out, (rc, out)
def p_maxlen():
    c = dict(VALID); c["name"] = "abcdefghijk"
    rc, out = run(c, S); return rc != 0 and "name" in out, (rc, out)
def p_pattern():
    c = dict(VALID); c["name"] = "App1"
    rc, out = run(c, S); return rc != 0 and "name" in out, (rc, out)
def p_nested_dot():
    c = json.loads(json.dumps(VALID)); c["server"]["tls"]["level"] = 9
    rc, out = run(c, S); return rc != 0 and "server.tls.level" in out, (rc, out)
def p_nested_required_dot():
    c = json.loads(json.dumps(VALID)); del c["server"]["tls"]["cert"]
    rc, out = run(c, S); return rc != 0 and "server.tls.cert" in out, (rc, out)
def p_nested_type_dot():
    c = json.loads(json.dumps(VALID)); c["server"]["host"] = 5
    rc, out = run(c, S); return rc != 0 and "server.host" in out, (rc, out)
def p_all_errors():
    c = {"name": "A", "ratio": 5, "debug": "yes", "mode": "x", "server": {"tls": {"level": 9}}}
    rc, out = run(c, S)
    needles = ["port", "name", "ratio", "debug", "mode", "server.host", "server.tls.cert", "server.tls.level"]
    return rc != 0 and all(n in out for n in needles), (rc, out)
def p_multi_same_field():
    c = dict(VALID); c["name"] = "A"  # too short AND pattern fail
    rc, out = run(c, S)
    lines = [l for l in out.splitlines() if "name" in l]
    return rc != 0 and len(lines) >= 2, (rc, out)
def p_missing_file():
    rc, out = run(VALID, S, args=["/nonexistent/c.json", "/nonexistent/s.json"])
    return rc not in (0, 1) and "Traceback" not in out, (rc, out)
def p_bad_json():
    rc, out = run("{bad", S, raw_config=True)
    return rc not in (0,) and "Traceback" not in out, (rc, out)
def p_bad_schema_json():
    rc, out = run(VALID, "{bad", raw_schema=True)
    return rc not in (0,) and "Traceback" not in out, (rc, out)
def p_no_args():
    rc, out = run(VALID, S, args=[])
    return rc != 0 and "Traceback" not in out, (rc, out)
def p_invalid_regex():
    rc, out = run({"a": "x"}, {"type": "object", "properties": {"a": {"type": "string", "pattern": "("}}})
    return rc != 0 and "Traceback" not in out, (rc, out)
def p_unknown_type():
    rc, out = run({"a": "x"}, {"type": "object", "properties": {"a": {"type": "strng"}}})
    return rc != 0 and "Traceback" not in out, (rc, out)
def p_wrong_root_type():
    rc, out = run([1, 2], S)
    return rc != 0 and "Traceback" not in out, (rc, out)
def p_single_file_stdlib():
    files = [f for f in os.listdir(side) if f.endswith(".py")]
    src = open(script).read()
    import re as _re
    mods = set(_re.findall(r"^\s*(?:import|from)\s+([A-Za-z_]+)", src, _re.M))
    std = {"argparse","json","re","sys","os","typing","pathlib","__future__","dataclasses","collections"}
    return files == ["config_validator.py"] and mods <= std, (files, sorted(mods))
def p_bad_schema_structure():
    rc, out = run({"a": 1}, {"type": "object", "properties": {"a": {"type": "integer", "minimum": "x"}}})
    return "Traceback" not in out, (rc, out)

def p_non_utf8():
    rc, out = run("\udcff{", S, raw_config=True) if False else (None, None)
    d = tempfile.mkdtemp(); cp = os.path.join(d, "c.json"); sp = os.path.join(d, "s.json")
    open(cp, "wb").write(b"\xff\xfe{"); open(sp, "w").write(json.dumps(S))
    p = subprocess.run([sys.executable, script, cp, sp], capture_output=True, text=True, timeout=30)
    out = p.stdout + p.stderr
    return p.returncode not in (0, 1) and "Traceback" not in out, (p.returncode, out)
def p_nondict_subschema():
    rc, out = run({"a": 1}, {"type": "object", "properties": {"a": "int"}})
    return rc != 0 and "Traceback" not in out, (rc, out)

for pid, fn in [
    ("P01_valid_config_exit0", p_valid), ("P02_required_missing", p_required),
    ("P03_type_string", type_probe("name", 5)), ("P04_type_integer", type_probe("port", "80")),
    ("P05_type_number", type_probe("ratio", "x")), ("P06_type_boolean", type_probe("debug", "yes")),
    ("P07_type_array", type_probe("tags", {})), ("P08_type_object", type_probe("server", [])),
    ("P09_bool_not_integer", p_bool_not_int), ("P10_int_is_number", p_int_accepts_number_ok),
    ("P11_float_not_integer", p_float_not_int), ("P12_enum", p_enum), ("P13_minimum", p_min),
    ("P14_maximum", p_max), ("P15_number_minimum", p_num_min), ("P16_boundaries_inclusive", p_boundary),
    ("P17_minLength", p_minlen), ("P18_maxLength", p_maxlen), ("P19_pattern", p_pattern),
    ("P20_nested_dot_constraint", p_nested_dot), ("P21_nested_dot_required", p_nested_required_dot),
    ("P22_nested_dot_type", p_nested_type_dot), ("P23_all_errors_reported", p_all_errors),
    ("P24_multiple_errors_same_field", p_multi_same_field), ("P25_missing_file_clean", p_missing_file),
    ("P26_malformed_config_clean", p_bad_json), ("P27_malformed_schema_clean", p_bad_schema_json),
    ("P28_no_args_usage", p_no_args), ("P29_invalid_regex_no_traceback", p_invalid_regex),
    ("P30_unknown_schema_type_rejected", p_unknown_type), ("P31_wrong_root_type", p_wrong_root_type),
    ("P32_single_file_stdlib", p_single_file_stdlib), ("P33_bad_schema_value_no_traceback", p_bad_schema_structure),
    ("P34_non_utf8_config_clean", p_non_utf8), ("P35_nondict_subschema_reported", p_nondict_subschema),
]:
    probe(pid, fn)

print(json.dumps({"results": results, "details": details}))
