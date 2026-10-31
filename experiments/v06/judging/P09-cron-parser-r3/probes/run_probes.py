"""Black-box probes. Usage: python3 -I run_probes.py <side_dir>"""
import json, subprocess, sys, os, tempfile, re, shutil
from datetime import datetime, timedelta, date

SIDE = os.path.abspath(sys.argv[1])
MON = "jan feb mar apr may jun jul aug sep oct nov dec".split()
DOW = "sun mon tue wed thu fri sat".split()
SPECS = [(0,59,None,0),(0,23,None,0),(1,31,None,0),(1,12,MON,1),(0,7,DOW,0)]

def rv(t, lo, hi, names, off):
    if names and t.lower() in names: return names.index(t.lower())+off
    return int(t)
def rfield(text, spec, idx):
    lo, hi, names, off = spec
    vals=set()
    for p in text.split(","):
        r, s, st = p.partition("/"); step=int(st) if s else 1
        if r=="*": a,b=lo,(6 if idx==4 else hi)
        elif "-" in r:
            x,_,y=r.partition("-"); a,b=rv(x,*spec),rv(y,*spec)
        else:
            a=rv(r,*spec); b=hi if s else a
        vals.update(range(a,b+1,step))
    if idx==4: vals={v%7 for v in vals}
    return vals
def ref(expr, start, n):
    f=expr.split(); F=[rfield(t,SPECS[i],i) for i,t in enumerate(f)]
    domstar=f[2].startswith("*"); dowstar=f[4].startswith("*")
    t=start.replace(second=0,microsecond=0)+timedelta(minutes=1)
    d=t.date(); out=[]
    while len(out)<n and d.year<t.year+60:
        if d.month in F[3]:
            a=d.day in F[2]; b=(d.isoweekday()%7) in F[4]
            ok=(a and b) if (domstar or dowstar) else (a or b)
            if ok:
                for h in sorted(F[1]):
                    for m in sorted(F[0]):
                        c=datetime(d.year,d.month,d.day,h,m)
                        if c>=t:
                            out.append(c)
                            if len(out)==n: return out
        d+=timedelta(days=1)
    return out

def run(*args, timeout=30):
    tmp=tempfile.mkdtemp()
    try:
        p=subprocess.run([sys.executable,"-I",os.path.join(SIDE,"cron_parser.py"),*args],
                         capture_output=True,text=True,timeout=timeout,cwd=tmp)
        return p.returncode,p.stdout,p.stderr
    except subprocess.TimeoutExpired:
        return "timeout","",""
    finally: shutil.rmtree(tmp)

def times(out):
    r=[]
    for line in out.splitlines():
        m=re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})",line)
        if m: r.append(datetime.strptime(m.group(1)+" "+m.group(2),"%Y-%m-%d %H:%M"))
    return r

def next_ok(expr, n):
    s1=datetime.now()
    args=["next",expr]+(["-n",str(n)] if n else [])
    code,out,err=run(*args)
    s2=datetime.now()
    got=times(out)
    if code!=0 or not got: return False
    k=n or len(got)
    if n is None and k<1: return False
    return got in (ref(expr,s1,k),ref(expr,s2,k))

def rejected(*args):
    code,out,err=run(*args)
    return code not in (0,"timeout") and "Traceback" not in err and err.strip()!=""

R={}
c,o,e=run("validate","*/15 9-17 * * mon-fri")
R["P01_validate_explains"]= c==0 and all(k in o.lower() for k in ["minute","hour","month"]) and ("day-of-month" in o.lower() or "day of month" in o.lower()) and ("day-of-week" in o.lower() or "day of week" in o.lower())
R["P02_validate_invalid_reports"]=rejected("validate","60 * * * *")
R["P03_six_fields_rejected"]=rejected("validate","0 0 * * * *")
R["P04_four_fields_rejected"]=rejected("validate","0 0 * *")
R["P05_month_names"]=next_ok("0 0 1 jan,jul *",3)
R["P06_dow_names_range"]=next_ok("30 9 * * mon-fri",7)
R["P07_step_star"]=next_ok("*/20 * * * *",5)
R["P08_range_step"]=next_ok("0 1-10/3 * * *",6)
R["P09_list"]=next_ok("5,10,15 * * * *",4)
R["P10_default_count"]=next_ok("* * * * *",None)
c,o,e=run("validate","0 0 30 2 *",timeout=15)
R["P11a_validate_feb30_error"]= c not in (0,"timeout") and "Traceback" not in e
c,o,e=run("next","0 0 30 2 *",timeout=15)
R["P11b_next_feb30_error_no_hang"]= c not in (0,"timeout") and "Traceback" not in e and not times(o)
c,o,e=run("next","0 0 31 4,6,9,11 *",timeout=15)
R["P12_next_31_in_30day_months_error"]= c not in (0,"timeout") and not times(o)
R["P13_dom31_skips_short_months"]=next_ok("0 0 31 * *",7)
R["P14_feb29_five_runs"]=next_ok("0 0 29 2 *",5)
R["P15_yearly_fifteen_runs"]=next_ok("0 0 1 1 *",15)
R["P16_dom_dow_or"]=next_ok("0 0 13 * fri",10)
bad=["*/0 * * * *","5-1 * * * *","a * * * *","1,,2 * * * *","* * * 13 *","* * * * 8","* * 0 * *","1/x * * * *","* 24 * * *"]
R["P17_malformed_rejected"]=all(rejected("validate",b) for b in bad)
R["P18_dow7_sunday"]=next_ok("0 0 * * 7",3)
R["P19_n_zero_rejected"]=rejected("next","* * * * *","-n","0")
R["P20_nonascii_digit_no_traceback"]=rejected("validate","² * * * *") and rejected("validate","١ * * * *")
R["P21_names_case_insensitive"]=next_ok("0 0 * JAN MON",3)
R["P22_n_count_large"]=next_ok("0 12 * * *",40)
src=open(os.path.join(SIDE,"cron_parser.py")).read()
std={"argparse","calendar","sys","datetime","re","os","time","itertools","functools","collections","typing","dataclasses","enum"}
mods={m for m in re.findall(r"^(?:from|import)\s+(\w+)",src,re.M)}
R["P23_stdlib_only"]=mods<=std
R["P24_single_file"]=os.path.isfile(os.path.join(SIDE,"cron_parser.py")) and not [f for f in os.listdir(SIDE) if f.endswith(".py") and f!="cron_parser.py"]
print(json.dumps({k:("pass" if v else "fail") for k,v in R.items()}))
