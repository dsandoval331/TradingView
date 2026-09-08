from pathlib import Path
import json, traceback, hashlib
from collections import defaultdict
import pandas as pd

from tr_platform.pmpd_v5.research_dataset import build_symbol_research_dataset

ROOT=Path.cwd()
PROTOCOL_PATH=ROOT/"PMPD_V5_9M_OOS_PROTOCOL_V1.json"
COVERAGE_PATH=ROOT/"pmpd_v5_9m_2026_timestamp_coverage_cert_v1.json"
OUT=ROOT/"pmpd_v5_9m_oos_frames_v1"
OUT.mkdir(parents=True,exist_ok=True)

protocol=json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
coverage=json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
start=pd.Timestamp(protocol["frozen_evaluation_window"]["start_date"])
end=pd.Timestamp(protocol["frozen_evaluation_window"]["end_date"])

def read_market_file(path):
    p=Path(path)
    if p.suffix.lower()==".parquet":
        return pd.read_parquet(p)
    if p.suffix.lower()==".csv":
        return pd.read_csv(p)
    raise ValueError(f"Unsupported format: {p}")

def frame_date_mask(df):
    if "trade_date" in df.columns:
        d=pd.to_datetime(df["trade_date"],errors="coerce").dt.tz_localize(None)
        return (d>=start)&(d<=end), "trade_date"
    for c in ["timestamp_et","timestamp_utc","timestamp","datetime"]:
        if c in df.columns:
            t=pd.to_datetime(df[c],errors="coerce",utc=True)
            d=t.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
            return (d>=start)&(d<=end), c
    return pd.Series(True,index=df.index), None

selected={}
for sym,v in coverage.get("per_symbol",{}).items():
    s=v.get("selected")
    if s and s.get("path"):
        selected[sym]=s["path"]

print("=== PMPD V5 9M OOS RESEARCH FRAME BUILD V1 ===")
print("PROTOCOL =",protocol["protocol_id"])
print("CANDIDATE =",protocol["candidate_code"])
print("WINDOW =",protocol["frozen_evaluation_window"])
print("SELECTED_SYMBOLS =",len(selected))
print("OUT =",OUT)

manifest=[]
schema_registry=defaultdict(set)
errors=[]
frame_parts=defaultdict(list)

for i,(sym,path) in enumerate(sorted(selected.items()),1):
    try:
        bars=read_market_file(path)
        result=build_symbol_research_dataset(bars,symbol=sym)
        if not isinstance(result,dict):
            raise TypeError(f"Expected dict, got {type(result)}")
        row={"symbol":sym,"source":path,"input_rows":len(bars),"frames":{}}
        for name,df in result.items():
            if not isinstance(df,pd.DataFrame):
                continue
            mask,date_source=frame_date_mask(df)
            x=df.loc[mask].copy()
            if "symbol" not in x.columns:
                x["symbol"]=sym
            x["oos_protocol_id"]=protocol["protocol_id"]
            x["oos_candidate_code"]=protocol["candidate_code"]
            frame_parts[name].append(x)
            schema_registry[name].add(tuple(map(str,x.columns)))
            row["frames"][name]={"rows":len(x),"date_source":date_source,"columns":list(map(str,x.columns))}
        manifest.append(row)
        print(f"[{i:03d}/{len(selected)}] {sym}: PASS " +
              " ".join(f"{k}={v['rows']}" for k,v in row["frames"].items()))
    except Exception as e:
        errors.append({"symbol":sym,"source":path,"error":repr(e),"traceback":traceback.format_exc()})
        print(f"[{i:03d}/{len(selected)}] {sym}: FAIL {e!r}")

combined={}
for name,parts in frame_parts.items():
    if not parts:
        continue
    df=pd.concat(parts,ignore_index=True,sort=False)
    p=OUT/f"{name}.parquet"
    df.to_parquet(p,index=False)
    combined[name]={"rows":len(df),"columns":list(map(str,df.columns)),"path":str(p)}
    print("COMBINED_FRAME",name,"ROWS",len(df),"COLS",len(df.columns),"PATH",p)

payload={
    "protocol_id":protocol["protocol_id"],
    "candidate_code":protocol["candidate_code"],
    "window":protocol["frozen_evaluation_window"],
    "symbols_expected":len(selected),
    "symbols_passed":len(manifest),
    "symbols_failed":len(errors),
    "errors":errors,
    "combined_frames":combined,
    "schema_variant_counts":{k:len(v) for k,v in schema_registry.items()},
    "outcomes_summarized":False,
    "candidate_modified":False,
    "threshold_tuning":False,
    "score_fitting":False,
    "production_rule_authorized":False
}
m=OUT/"build_manifest.json"
m.write_text(json.dumps(payload,indent=2),encoding="utf-8")

print("SYMBOLS_PASSED =",payload["symbols_passed"])
print("SYMBOLS_FAILED =",payload["symbols_failed"])
print("FRAME_NAMES =",sorted(combined))
print("SCHEMA_VARIANT_COUNTS =",payload["schema_variant_counts"])
print("MANIFEST =",m)
print("OUTCOMES_SUMMARIZED=False")
print("CANDIDATE_MODIFIED=False")
print("THRESHOLD_TUNING=False")
print("SCORE_FITTING=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_OOS_FRAME_BUILD_GATE=PASS" if len(errors)==0 and len(manifest)==len(selected) else "9M_OOS_FRAME_BUILD_GATE=REVIEW")
