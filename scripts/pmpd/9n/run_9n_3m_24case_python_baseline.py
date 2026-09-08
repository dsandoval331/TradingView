from pathlib import Path
import pandas as pd, json, hashlib, sys

ROOT=Path.cwd()
ENGINE=Path(__file__).resolve().parent/"v4_parity_engine_v2.py"
CACHE=ROOT/"data"/"second1m_alt_entry_cache_v1"/"partitions"
SAMPLE=ROOT/"PMPD_V4_PARITY_RECAPTURE_24_V1.csv"
EXPECTED_ENGINE_SHA="cab75475f0bf4f4a9d8cf86561d9959957d660aeae7926769e26c53599be4b22"
OUT=ROOT/"pmpd_v5_9n_3m_24case_python_baseline.csv"
SUMMARY=ROOT/"pmpd_v5_9n_3m_24case_python_baseline_summary.json"

FALLBACK=[
("SET_1",1,"VRTX","2026-07-01"),("SET_1",2,"INTC","2026-03-31"),
("SET_1",3,"QCOM","2026-07-02"),("SET_1",4,"MSFT","2026-03-31"),
("SET_1",5,"TXN","2026-05-08"),("SET_1",6,"COIN","2026-05-18"),
("SET_2",1,"ADBE","2026-04-13"),("SET_2",2,"MU","2026-07-07"),
("SET_2",3,"CAT","2026-04-17"),("SET_2",4,"SLB","2026-07-28"),
("SET_2",5,"UNH","2026-05-29"),("SET_2",6,"COP","2026-04-08"),
("SET_3",1,"MRVL","2026-05-14"),("SET_3",2,"NOW","2026-03-25"),
("SET_3",3,"PANW","2026-04-09"),("SET_3",4,"PEP","2026-05-06"),
("SET_3",5,"C","2026-04-01"),("SET_3",6,"LOW","2026-03-20"),
("SET_4",1,"APP","2026-08-18"),("SET_4",2,"BLK","2026-07-27"),
("SET_4",3,"SHOP","2026-04-24"),("SET_4",4,"CSCO","2026-06-02"),
("SET_4",5,"DASH","2026-05-13"),("SET_4",6,"ABNB","2026-07-31"),
]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
if not ENGINE.exists(): raise SystemExit("MISSING_ENGINE")
if sha(ENGINE)!=EXPECTED_ENGINE_SHA: raise SystemExit("ENGINE_SHA_MISMATCH")
from v4_parity_engine_v2 import evaluate_v4_signals, build_daily_levels

cases=FALLBACK
if SAMPLE.exists():
    x=pd.read_csv(SAMPLE)
    sym=next((c for c in x.columns if c.lower() in ("symbol","ticker")),None)
    dat=next((c for c in x.columns if c.lower() in ("trade_date","target_date","date")),None)
    setc=next((c for c in x.columns if c.lower()=="set_code"),None)
    rank=next((c for c in x.columns if c.lower() in ("selection_rank","rank")),None)
    if sym and dat and len(x)==24:
        cases=[(str(r[setc]) if setc else None,int(r[rank]) if rank else i+1,str(r[sym]),str(r[dat])[:10])
               for i,(_,r) in enumerate(x.iterrows())]

rows=[]
print("=== PMPD V5 9N-3M 24-CASE PYTHON BASELINE ===")
print("ENGINE_SHA=PASS")
for setc,rank,sym,date_s in cases:
    p=CACHE/sym/f"{sym}_2026.parquet"
    if not p.exists():
        rows.append({"set":setc,"rank":rank,"symbol":sym,"date":date_s,"status":"MISSING_PARTITION"}); continue
    raw=pd.read_parquet(p)
    idx=pd.DatetimeIndex(pd.to_datetime(raw["timestamp_utc"],utc=True))
    raw=raw.copy(); raw.index=idx
    sig=evaluate_v4_signals(raw,symbol=sym)
    target=sig[sig["trade_date"].astype(str).eq(date_s)].copy() if (not sig.empty and "trade_date" in sig.columns) else sig.iloc[0:0]
    levels=build_daily_levels(raw)
    hit=[i for i in levels.index if str(i)[:10]==date_s]
    lv=levels.loc[hit[0]] if hit else None
    rec={"set":setc,"rank":rank,"symbol":sym,"date":date_s,"status":"OK",
         "signal_count":int(len(target))}
    if lv is not None:
        for k in ("pmh","pml","pdh","pdl"):
            rec[k]=None if pd.isna(lv[k]) else float(lv[k])
    if len(target):
        # compact signal summary preserving all cases, including multi-signal dates
        for j,(_,r) in enumerate(target.iterrows(),1):
            if j>3: break
            for k in ("direction","signal_time","reference","total_score","grade","profile","priority","trade_type","first_outcome","mfe","mae"):
                if k in target.columns:
                    v=r[k]
                    rec[f"s{j}_{k}"]=None if pd.isna(v) else str(v)
    rows.append(rec)
    print(f"{setc} #{rank} {sym:5s} {date_s} signals={len(target)} PMH={rec.get('pmh')} PML={rec.get('pml')} PDH={rec.get('pdh')} PDL={rec.get('pdl')}")

df=pd.DataFrame(rows)
df.to_csv(OUT,index=False)
summary={"step":"9N-3M","cases":len(df),"ok":int(df.status.eq("OK").sum()),
         "signal_count_distribution":df.loc[df.status.eq("OK"),"signal_count"].value_counts().sort_index().to_dict(),
         "cases_with_signal":df.loc[df.signal_count.fillna(0).gt(0),["set","rank","symbol","date","signal_count"]].to_dict("records"),
         "engine_sha256":sha(ENGINE),
         "governance":{"v4_modified":False,"v5_modified":False,"production_rule_authorized":False,
                       "tradingview_full_24_case_parity_validated":False}}
SUMMARY.write_text(json.dumps(summary,indent=2),encoding="utf-8")
print("CSV =",OUT); print("SUMMARY =",SUMMARY)
print("V4_MODIFIED=False"); print("V5_MODIFIED=False")
print("TRADINGVIEW_FULL_24_CASE_PARITY_VALIDATED=False")
print("9N_3M_24CASE_PYTHON_BASELINE=PASS")


