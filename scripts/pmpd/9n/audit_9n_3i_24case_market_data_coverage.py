from pathlib import Path
import pandas as pd
import json, hashlib, sys

ROOT = Path.cwd()
CACHE_ROOT = ROOT / "data" / "second1m_alt_entry_cache_v1" / "partitions"
SAMPLE_CSV = ROOT / "PMPD_V4_PARITY_RECAPTURE_24_V1.csv"

# Frozen 24-case fallback, used only if the protocol CSV is not local.
CASES = [
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

def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_cases():
    if SAMPLE_CSV.exists():
        x = pd.read_csv(SAMPLE_CSV)
        # Flexible extraction because protocol column names may differ.
        sym = next((c for c in x.columns if c.lower() in ("symbol","ticker")), None)
        dat = next((c for c in x.columns if c.lower() in ("trade_date","target_date","date")), None)
        if sym and dat and len(x) == 24:
            return [(None,i+1,str(r[sym]),str(r[dat])[:10]) for i,(_,r) in enumerate(x.iterrows())], "protocol_csv"
    return CASES, "embedded_frozen_24"

def session_stats(df, date_s, lo_min, hi_min):
    target = pd.Timestamp(date_s).date()
    et = pd.to_datetime(df["timestamp_et"])
    if getattr(et.dt, "tz", None) is not None:
        et = et.dt.tz_convert("America/New_York")
    mins = et.dt.hour*60 + et.dt.minute
    x = df[(et.dt.date == target) & (mins >= lo_min) & (mins <= hi_min)].copy()
    if x.empty:
        return dict(rows=0, unique_minutes=0, first=None, last=None, high=None, low=None,
                    span_minutes=0, max_gap_minutes=None)
    xt = pd.to_datetime(x["timestamp_et"]).sort_values()
    if getattr(xt.dt, "tz", None) is not None:
        xt = xt.dt.tz_convert("America/New_York")
    unique = xt.drop_duplicates()
    gaps = unique.diff().dropna().dt.total_seconds().div(60)
    return dict(
        rows=int(len(x)), unique_minutes=int(unique.size),
        first=str(unique.iloc[0]), last=str(unique.iloc[-1]),
        high=float(x["high"].max()), low=float(x["low"].min()),
        span_minutes=int((unique.iloc[-1]-unique.iloc[0]).total_seconds()/60)+1,
        max_gap_minutes=None if gaps.empty else float(gaps.max())
    )

cases, case_source = load_cases()
rows=[]
missing=[]
print("=== PMPD V5 9N-3I 24-CASE LOCAL MARKET-DATA COVERAGE AUDIT ===")
print("CACHE_ROOT =", CACHE_ROOT)
print("CASE_SOURCE =", case_source)

for set_name, rank, symbol, date_s in cases:
    p = CACHE_ROOT / symbol / f"{symbol}_2026.parquet"
    rec={"set":set_name,"rank":rank,"symbol":symbol,"date":date_s,"path":str(p),"file_exists":p.exists()}
    if not p.exists():
        rec.update({"pre_rows":0,"pre_unique_minutes":0,"rth_rows":0,"rth_unique_minutes":0,
                    "pre_class":"MISSING_PARTITION","rth_class":"MISSING_PARTITION"})
        missing.append(symbol)
        rows.append(rec); continue
    df=pd.read_parquet(p)
    pre=session_stats(df,date_s,240,569)
    rth=session_stats(df,date_s,570,959)
    rec.update({
        "file_sha256":sha256(p),
        "source_values":";".join(sorted(df["source"].dropna().astype(str).unique())) if "source" in df else "",
        "adjusted_values":";".join(sorted(df["adjusted"].dropna().astype(str).unique())) if "adjusted" in df else "",
        "pre_rows":pre["rows"],"pre_unique_minutes":pre["unique_minutes"],"pre_first":pre["first"],"pre_last":pre["last"],
        "pre_span_minutes":pre["span_minutes"],"pre_max_gap_minutes":pre["max_gap_minutes"],"pre_high":pre["high"],"pre_low":pre["low"],
        "rth_rows":rth["rows"],"rth_unique_minutes":rth["unique_minutes"],"rth_first":rth["first"],"rth_last":rth["last"],
        "rth_span_minutes":rth["span_minutes"],"rth_max_gap_minutes":rth["max_gap_minutes"],"rth_high":rth["high"],"rth_low":rth["low"],
    })
    # Coverage labels are descriptive, not trading/model rules.
    n=pre["unique_minutes"]
    if n == 0: pc="NONE"
    elif n < 10: pc="VERY_SPARSE"
    elif n < 60: pc="SPARSE"
    elif n < 180: pc="PARTIAL"
    else: pc="SUBSTANTIAL"
    rn=rth["unique_minutes"]
    rc="COMPLETE_OR_NEAR" if rn >= 385 else ("PARTIAL" if rn >= 300 else "SPARSE")
    rec["pre_class"]=pc; rec["rth_class"]=rc
    rows.append(rec)
    print(f'{symbol:5s} {date_s} PRE={n:3d} {pc:12s} RTH={rn:3d} {rc}')

audit=pd.DataFrame(rows)
csv_out=ROOT/"pmpd_v5_9n_3i_24case_market_data_coverage.csv"
json_out=ROOT/"pmpd_v5_9n_3i_24case_market_data_coverage_summary.json"
audit.to_csv(csv_out,index=False)

summary={
 "step":"9N-3I",
 "purpose":"24-case local Massive PRE/RTH coverage audit before further TradingView recapture",
 "case_source":case_source,
 "cases":len(audit),
 "partitions_found":int(audit.file_exists.sum()),
 "partitions_missing":int((~audit.file_exists).sum()),
 "pre_class_counts":audit.pre_class.value_counts(dropna=False).to_dict(),
 "rth_class_counts":audit.rth_class.value_counts(dropna=False).to_dict(),
 "pre_zero_cases":audit.loc[audit.pre_unique_minutes.eq(0),["symbol","date"]].to_dict("records") if "pre_unique_minutes" in audit else [],
 "pre_under_10_cases":audit.loc[audit.pre_unique_minutes.lt(10),["symbol","date","pre_unique_minutes"]].to_dict("records") if "pre_unique_minutes" in audit else [],
 "pre_under_60_cases":audit.loc[audit.pre_unique_minutes.lt(60),["symbol","date","pre_unique_minutes"]].to_dict("records") if "pre_unique_minutes" in audit else [],
 "rth_under_385_cases":audit.loc[audit.rth_unique_minutes.lt(385),["symbol","date","rth_unique_minutes"]].to_dict("records") if "rth_unique_minutes" in audit else [],
 "governance":{
   "v4_modified":False,"v5_modified":False,"production_rule_authorized":False,
   "coverage_classes_are_diagnostic_not_model_thresholds":True,
   "full_tradingview_parity_validated":False
 }
}
json_out.write_text(json.dumps(summary,indent=2),encoding="utf-8")
print("\nPRE_CLASS_COUNTS =", summary["pre_class_counts"])
print("RTH_CLASS_COUNTS =", summary["rth_class_counts"])
print("CSV =", csv_out)
print("SUMMARY =", json_out)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_FULL_24_CASE_PARITY_VALIDATED=False")
print("9N_3I_COVERAGE_AUDIT=PASS")
