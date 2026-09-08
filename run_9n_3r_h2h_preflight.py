from pathlib import Path
import json, hashlib, pandas as pd, re

ROOT=Path.cwd()
ENGINE=ROOT/"v4_parity_engine_v2.py"
CACHE=ROOT/"data"/"second1m_alt_entry_cache_v1"/"partitions"
EXPECTED_ENGINE_SHA="cab75475f0bf4f4a9d8cf86561d9959957d660aeae7926769e26c53599be4b22"
OUT=ROOT/"pmpd_v5_9n_3r_h2h_preflight.json"

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

print("=== PMPD V5 9N-3R H2H PREFLIGHT ===")
if not ENGINE.exists(): raise SystemExit("MISSING_ENGINE")
engine_sha=sha(ENGINE)
print("ENGINE_SHA =",engine_sha)
print("ENGINE_SHA_MATCH =",engine_sha==EXPECTED_ENGINE_SHA)
if engine_sha!=EXPECTED_ENGINE_SHA: raise SystemExit("ENGINE_SHA_MISMATCH")

# 2026 Massive partitions
parts=list(CACHE.glob("*/*_2026.parquet")) if CACHE.exists() else []
symbols=sorted({p.parent.name for p in parts})
print("2026_PARTITIONS =",len(parts))
print("2026_SYMBOLS =",len(symbols))

# Search only plausible V5/OOS result artifacts; ignore .venv/.git and large unrelated trees.
cands=[]
skip={".git",".venv","node_modules","__pycache__"}
for p in ROOT.rglob("*"):
    if not p.is_file() or any(x in skip for x in p.parts): continue
    name=p.name.lower()
    if p.suffix.lower() not in {".parquet",".csv",".json"}: continue
    if not any(t in name for t in ("9m","oos","dp4","candidate")): continue
    cands.append(p)

artifacts=[]
for p in cands:
    rec={"path":str(p),"suffix":p.suffix.lower(),"size":p.stat().st_size}
    try:
        if p.suffix.lower()==".parquet":
            d=pd.read_parquet(p)
            rec["rows"]=len(d); rec["columns"]=list(map(str,d.columns))
        elif p.suffix.lower()==".csv":
            d=pd.read_csv(p,nrows=5)
            rec["columns"]=list(map(str,d.columns))
        else:
            obj=json.loads(p.read_text(encoding="utf-8"))
            rec["json_type"]=type(obj).__name__
            if isinstance(obj,dict): rec["keys"]=list(obj.keys())[:80]
    except Exception as e:
        rec["inspect_error"]=type(e).__name__+": "+str(e)[:300]
    cols=[c.lower() for c in rec.get("columns",[])]
    rec["has_symbol"]=any(c in cols for c in ("symbol","ticker"))
    rec["has_date"]=any(c in cols for c in ("trade_date","date","event_date"))
    rec["has_outcome"]=any(("outcome" in c or "favorable_first" in c or "adverse_first" in c) for c in cols)
    rec["has_direction"]=any(c in cols for c in ("direction","side","signal_direction"))
    artifacts.append(rec)

likely=[a for a in artifacts if a.get("has_symbol") and a.get("has_date") and (a.get("has_outcome") or a.get("has_direction"))]
print("V5_CANDIDATE_ARTIFACTS_INSPECTED =",len(artifacts))
print("LIKELY_H2H_INPUTS =",len(likely))
for a in likely[:20]:
    print("LIKELY =",a["path"],"rows=",a.get("rows"),"outcome=",a.get("has_outcome"),"direction=",a.get("has_direction"))

result={
 "step":"9N-3R",
 "engine_sha256":engine_sha,
 "engine_sha_match":engine_sha==EXPECTED_ENGINE_SHA,
 "massive_2026_partition_count":len(parts),
 "massive_2026_symbol_count":len(symbols),
 "artifacts_inspected":artifacts,
 "likely_h2h_inputs":likely,
 "parity_closure_status":"RESEARCH_CERTIFIED_WITH_DOCUMENTED_SOURCE_LIMITATION",
 "full_24case_tradingview_parity":False,
 "v4_modified":False,"v5_modified":False,"production_rule_authorized":False
}
OUT.write_text(json.dumps(result,indent=2),encoding="utf-8")
print("REPORT =",OUT)
print("9N_3R_H2H_PREFLIGHT=PASS")
