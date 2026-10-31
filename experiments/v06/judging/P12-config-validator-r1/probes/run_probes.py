import json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(side, config, schema, raw_config=None, raw_schema=None, args=None):
    d = tempfile.mkdtemp()
    c = os.path.join(d, "c.json"); s = os.path.join(d, "s.json")
    open(c, "w").write(raw_config if raw_config is not None else json.dumps(config))
    open(s, "w").write(raw_schema if raw_schema is not None else json.dumps(schema))
    a = args if args is not None else [c, s]
    a = [x.replace("{c}", c).replace("{s}", s) if isinstance(x,str) else x for x in a]
    p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, side, "config_validator.py")] + a,
                       capture_output=True, text=True, timeout=20, cwd=d)
    return p.returncode, p.stdout, p.stderr
S = {"type":"object","required":["name","port"],"properties":{
  "name":{"type":"string","minLength":3,"maxLength":10,"pattern":"^[a-z]+$"},
  "port":{"type":"integer","minimum":1,"maximum":65535},
  "ratio":{"type":"number","minimum":0,"maximum":1},
  "debug":{"type":"boolean"},
  "tags":{"type":"array"},
  "mode":{"enum":["dev","prod"]},
  "db":{"type":"object","required":["host"],"properties":{"host":{"type":"string"},
        "pool":{"type":"object","required":["size"],"properties":{"size":{"type":"integer","minimum":1}}}}}}}
VALID = {"name":"app","port":80,"ratio":0.5,"debug":True,"tags":[],"mode":"dev","db":{"host":"h","pool":{"size":2}}}
def P(cond): return "pass" if cond else "fail"
def probes(side):
    r = {}
    rc,o,e = run(side, VALID, S); r["P01_valid_exit0"] = P(rc==0 and "Traceback" not in e)
    rc,o,e = run(side, {"port":80}, S); r["P02_required_missing"] = P(rc!=0 and "name" in o+e)
    for k,(cfg) in {"string":{"name":5},"integer":{"port":"x"},"number":{"ratio":"x"},"boolean":{"debug":"yes"},"array":{"tags":{}},"object":{"db":[]}}.items():
        c = dict(VALID); c.update(cfg); rc,o,e = run(side, c, S)
        key = list(cfg)[0]
        r["P03_type_"+k] = P(rc==1 and key in o+e)
    c = dict(VALID); c["port"]=1.5; rc,o,e = run(side,c,S); r["P04_integer_rejects_float"] = P(rc==1 and "port" in o)
    c = dict(VALID); c["port"]=True; rc,o,e = run(side,c,S); r["P05_integer_rejects_bool"] = P(rc==1 and "port" in o)
    c = dict(VALID); c["mode"]="test"; rc,o,e = run(side,c,S); r["P06_enum"] = P(rc==1 and "mode" in o)
    c = dict(VALID); c["port"]=0; rc,o,e = run(side,c,S); r["P07_minimum"] = P(rc==1 and "port" in o)
    c = dict(VALID); c["port"]=70000; rc,o,e = run(side,c,S); r["P08_maximum"] = P(rc==1 and "port" in o)
    c = dict(VALID); c["name"]="ab"; rc,o,e = run(side,c,S); r["P09_minLength"] = P(rc==1 and "name" in o)
    c = dict(VALID); c["name"]="abcdefghijkl"; rc,o,e = run(side,c,S); r["P10_maxLength"] = P(rc==1 and "name" in o)
    c = dict(VALID); c["name"]="ABC"; rc,o,e = run(side,c,S); r["P11_pattern"] = P(rc==1 and "name" in o)
    c = dict(VALID); c["db"]={"pool":{"size":0}}; rc,o,e = run(side,c,S)
    r["P12_nested_dot_required"] = P(rc==1 and "db.host" in o)
    r["P13_nested_dot_deep"] = P(rc==1 and "db.pool.size" in o)
    c = {"name":"AB","port":0,"ratio":2,"debug":"x","mode":"q","db":{"pool":{}}}; rc,o,e = run(side,c,S)
    found = [x for x in ["name","port","ratio","debug","mode","db.host","db.pool.size"] if x in o]
    r["P14_all_errors_reported"] = P(rc==1 and len(found)==7)
    r["P15_multi_errors_same_field"] = P(o.count("name")>=2)  # minLength + pattern
    rc,o,e = run(side,None,S,args=["/nonexistent/x.json","{s}"]); r["P16_missing_file_graceful"] = P(rc not in (0,1) and "Traceback" not in e)
    rc,o,e = run(side,None,S,raw_config="{bad"); r["P17_bad_json_graceful"] = P(rc not in (0,1) and "Traceback" not in e)
    rc,o,e = run(side,None,S,args=[]); r["P18_usage_error"] = P(rc!=0 and "Traceback" not in e)
    rc,o,e = run(side,VALID,{"type":"object","properties":{"name":{"pattern":"("}}}); r["P19_bad_regex_no_traceback"] = P("Traceback" not in e)
    rc,o,e = run(side,{"flag":True},{"type":"object","properties":{"flag":{"enum":[1]}}}); r["P20_enum_true_not_1"] = P(rc==1)
    rc,o,e = run(side,{"a":1},{"type":"object","properties":{"a":"string"}}); r["P21_malformed_subschema_no_traceback"] = P("Traceback" not in e)
    src = open(os.path.join(ROOT, side, "config_validator.py")).read()
    import re as _re
    mods = set(_re.findall(r"^\s*(?:import|from)\s+(\w+)", src, _re.M))
    r["P22_stdlib_only"] = P(all(m in {"json","re","sys","argparse","os"} for m in mods))
    return r
res = {s: probes(s) for s in ("A","B")}
json.dump(res, open(os.path.join(ROOT,"probes","results.json"),"w"), indent=1)
for k in res["A"]: print(k, res["A"][k], res["B"][k])
