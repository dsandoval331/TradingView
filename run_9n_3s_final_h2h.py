from pathlib import Path
import json, hashlib, math
import numpy as np
import pandas as pd
import v4_parity_engine_v2 as v4

ROOT=Path.cwd()
CACHE=ROOT/"data"/"second1m_alt_entry_cache_v1"/"partitions"
V5_PATH=ROOT/"pmpd_v5_9m_oos_candidate_dp4_v1.parquet"
ENGINE=ROOT/"v4_parity_engine_v2.py"
EXPECTED_ENGINE_SHA="cab75475f0bf4f4a9d8cf86561d9959957d660aeae7926769e26c53599be4b22"

START=pd.Timestamp("2026-01-05").date()
END=pd.Timestamp("2026-09-02").date()
BOOT_REPS=10_000
SEED=9062026

OUT_V4=ROOT/"pmpd_v5_9n_3s_v4_events_2026.parquet"
OUT_SYMBOL=ROOT/"pmpd_v5_9n_3s_symbol_h2h.csv"
OUT_MONTH=ROOT/"pmpd_v5_9n_3s_monthly_h2h.csv"
OUT_SUMMARY=ROOT/"pmpd_v5_9n_3s_h2h_summary.json"

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def pick(cols, candidates, label, required=True):
    low={str(c).lower():c for c in cols}
    for x in candidates:
        if x.lower() in low: return low[x.lower()]
    if required:
        raise RuntimeError(f"Could not identify {label}. Columns={list(cols)}")
    return None

def normalize_outcome_series(s):
    x=s.astype(str).str.upper().str.strip()
    # Preserve canonical labels and tolerate common variants.
    mapping={
        "FAVORABLE":"FAVORABLE_FIRST","WIN":"FAVORABLE_FIRST","WIN_FIRST":"FAVORABLE_FIRST",
        "ADVERSE":"ADVERSE_FIRST","LOSS":"ADVERSE_FIRST","LOSS_FIRST":"ADVERSE_FIRST",
        "BOTH":"AMBIGUOUS_SAME_BAR","BOTH_AMBIGUOUS":"AMBIGUOUS_SAME_BAR",
        "AMBIGUOUS":"AMBIGUOUS_SAME_BAR","NEITHER":"UNRESOLVED"
    }
    return x.replace(mapping)

def counts_rate(df, outcome_col="outcome"):
    o=normalize_outcome_series(df[outcome_col])
    fav=int((o=="FAVORABLE_FIRST").sum())
    adv=int((o=="ADVERSE_FIRST").sum())
    amb=int(o.isin(["AMBIGUOUS_SAME_BAR","BOTH"]).sum())
    unr=int(o.isin(["UNRESOLVED","NEITHER"]).sum())
    res=fav+adv
    return {
        "events":int(len(df)),"favorable_first":fav,"adverse_first":adv,
        "resolved":res,"ambiguous":amb,"unresolved":unr,
        "resolved_favorable_rate":None if res==0 else fav/res
    }

print("=== PMPD V5 9N-3S FINAL V4-vs-V5 HEAD-TO-HEAD ===")
if not ENGINE.exists(): raise SystemExit("MISSING_ENGINE")
if sha(ENGINE)!=EXPECTED_ENGINE_SHA: raise SystemExit("ENGINE_SHA_MISMATCH")
if not V5_PATH.exists(): raise SystemExit(f"MISSING_V5_ARTIFACT {V5_PATH}")
print("ENGINE_SHA=PASS")
print("V5_ARTIFACT =",V5_PATH)

# ----------------------
# V5 frozen OOS adapter
# ----------------------
v5raw=pd.read_parquet(V5_PATH)
print("V5_ROWS_RAW =",len(v5raw))
print("V5_COLUMNS =",list(v5raw.columns))

sym_c=pick(v5raw.columns,["symbol","ticker"],"V5 symbol")
date_c=pick(v5raw.columns,["trade_date","event_date","date"],"V5 date")
dir_c=pick(v5raw.columns,["direction","side","signal_direction"],"V5 direction")
out_c=pick(v5raw.columns,["outcome","first_outcome","outcome_class","resolved_outcome","benchmark_outcome"],"V5 outcome")

v5=pd.DataFrame({
    "symbol":v5raw[sym_c].astype(str),
    "trade_date":pd.to_datetime(v5raw[date_c]).dt.date,
    "direction":v5raw[dir_c].astype(str).str.upper(),
    "outcome":normalize_outcome_series(v5raw[out_c]),
})
v5=v5[v5.trade_date.between(START,END)].copy()
print("V5_ROWS_WINDOW =",len(v5))
print("V5_OUTCOMES =",v5.outcome.value_counts(dropna=False).to_dict())

# ----------------------
# V4 frozen reconstruction
# ----------------------
parts=sorted(CACHE.glob("*/*_2026.parquet"))
if len(parts)!=112:
    raise SystemExit(f"EXPECTED_112_PARTITIONS_FOUND_{len(parts)}")

v4frames=[]
for i,p in enumerate(parts,1):
    sym=p.parent.name
    print(f"[{i}/112] V4 {sym}")
    raw=pd.read_parquet(p).copy()
    if "timestamp_utc" not in raw.columns:
        raise RuntimeError(f"{sym}: missing timestamp_utc")
    raw.index=pd.DatetimeIndex(pd.to_datetime(raw["timestamp_utc"],utc=True))
    sig=v4.evaluate_v4_signals(raw,symbol=sym)
    if sig.empty: continue

    sdate=pick(sig.columns,["trade_date","date"],"V4 trade date")
    sdir=pick(sig.columns,["direction","side"],"V4 direction")
    sout=pick(sig.columns,["first_outcome","outcome"],"V4 outcome")

    x=pd.DataFrame({
        "symbol":sym,
        "trade_date":pd.to_datetime(sig[sdate]).dt.date,
        "direction":sig[sdir].astype(str).str.upper(),
        "outcome":normalize_outcome_series(sig[sout]),
    })
    # preserve optional audit fields
    for src,dst in [
        ("signal_timestamp_et","signal_timestamp_et"),
        ("reference_price","reference_price"),
        ("total_score","total_score"),
        ("grade","grade"),
        ("profile","profile"),
        ("priority","priority"),
        ("trade_type","trade_type"),
        ("mfe","mfe"),("mae","mae")
    ]:
        if src in sig.columns: x[dst]=sig[src].values
    x=x[x.trade_date.between(START,END)]
    if len(x): v4frames.append(x)

v4df=pd.concat(v4frames,ignore_index=True) if v4frames else pd.DataFrame(columns=["symbol","trade_date","direction","outcome"])
v4df.to_parquet(OUT_V4,index=False)
print("V4_ROWS_WINDOW =",len(v4df))
print("V4_OUTCOMES =",v4df.outcome.value_counts(dropna=False).to_dict())

# Universe must be common 112.
u4=set(p.parent.name for p in parts)
u5=set(v5.symbol.unique())
common=sorted(u4 & u5)
if len(u4)!=112:
    raise RuntimeError("V4 universe not 112")
if len(common)!=112:
    missing=sorted(u4-u5)
    raise RuntimeError(f"V5 missing symbols from common universe: {missing}")

# ----------------------
# Overall / direction
# ----------------------
overall={"v4":counts_rate(v4df),"v5":counts_rate(v5)}
direction={}
for d in ["BULL","BEAR"]:
    direction[d]={"v4":counts_rate(v4df[v4df.direction.eq(d)]),
                  "v5":counts_rate(v5[v5.direction.eq(d)])}

# ----------------------
# Per-symbol paired table
# ----------------------
symrows=[]
for sym in common:
    a=counts_rate(v4df[v4df.symbol.eq(sym)])
    b=counts_rate(v5[v5.symbol.eq(sym)])
    symrows.append({
        "symbol":sym,
        "v4_events":a["events"],"v4_resolved":a["resolved"],"v4_favorable_first":a["favorable_first"],
        "v4_rate":a["resolved_favorable_rate"],
        "v5_events":b["events"],"v5_resolved":b["resolved"],"v5_favorable_first":b["favorable_first"],
        "v5_rate":b["resolved_favorable_rate"],
        "rate_diff_v5_minus_v4":(
            None if a["resolved_favorable_rate"] is None or b["resolved_favorable_rate"] is None
            else b["resolved_favorable_rate"]-a["resolved_favorable_rate"]
        )
    })
symdf=pd.DataFrame(symrows)
symdf.to_csv(OUT_SYMBOL,index=False)

valid=symdf.rate_diff_v5_minus_v4.notna()
frac_symbols_v5_gt_v4=None if not valid.any() else float((symdf.loc[valid,"rate_diff_v5_minus_v4"]>0).mean())

# ----------------------
# Paired symbol-cluster bootstrap
# Resample 112 symbols with replacement. Each occurrence contributes that
# symbol's full event cluster to both V4 and V5.
# ----------------------
arr=symdf.set_index("symbol").loc[common]
v4f=arr.v4_favorable_first.to_numpy(float)
v4r=arr.v4_resolved.to_numpy(float)
v5f=arr.v5_favorable_first.to_numpy(float)
v5r=arr.v5_resolved.to_numpy(float)

rng=np.random.default_rng(SEED)
diffs=np.empty(BOOT_REPS,float)
n=len(common)
for i in range(BOOT_REPS):
    idx=rng.integers(0,n,size=n)
    a_r=v4r[idx].sum(); b_r=v5r[idx].sum()
    if a_r<=0 or b_r<=0:
        diffs[i]=np.nan
    else:
        diffs[i]=(v5f[idx].sum()/b_r)-(v4f[idx].sum()/a_r)

good=diffs[~np.isnan(diffs)]
if len(good)!=BOOT_REPS:
    raise RuntimeError("Bootstrap produced invalid replicates")
lo,med,hi=np.quantile(good,[0.025,0.5,0.975])
point=overall["v5"]["resolved_favorable_rate"]-overall["v4"]["resolved_favorable_rate"]

if lo>0:
    winner="V5_WINS"
elif hi<0:
    winner="V4_WINS"
else:
    winner="NO_CLEAR_WINNER"

# ----------------------
# Monthly
# ----------------------
def monthly_table(df,label):
    x=df.copy()
    x["month"]=pd.to_datetime(x.trade_date).dt.to_period("M").astype(str)
    out=[]
    for m,g in x.groupby("month"):
        c=counts_rate(g)
        out.append({"month":m,f"{label}_events":c["events"],f"{label}_resolved":c["resolved"],
                    f"{label}_fav":c["favorable_first"],f"{label}_rate":c["resolved_favorable_rate"],
                    f"{label}_ambiguous":c["ambiguous"],f"{label}_unresolved":c["unresolved"]})
    return pd.DataFrame(out)
m4=monthly_table(v4df,"v4"); m5=monthly_table(v5,"v5")
months=pd.merge(m4,m5,on="month",how="outer").sort_values("month")
months["rate_diff_v5_minus_v4"]=months.v5_rate-months.v4_rate
months.to_csv(OUT_MONTH,index=False)

summary={
 "protocol":"PMPD_V5_9N_HEAD_TO_HEAD_PROTOCOL_V1",
 "window":{"start":str(START),"end":str(END)},
 "universe":{"v4_symbols":len(u4),"v5_symbols":len(u5),"common_symbols":len(common)},
 "overall":overall,
 "direction":direction,
 "primary_metric":{
    "v5_rate_minus_v4_rate":point,
    "bootstrap_reps":BOOT_REPS,
    "seed":SEED,
    "ci95_lower":float(lo),"bootstrap_median":float(med),"ci95_upper":float(hi),
    "classification":winner
 },
 "secondary":{
    "fraction_symbols_v5_rate_gt_v4":frac_symbols_v5_gt_v4,
    "v4_event_count":int(len(v4df)),
    "v5_event_count":int(len(v5)),
    "v5_minus_v4_event_count":int(len(v5)-len(v4df))
 },
 "artifacts":{
    "v4_events":str(OUT_V4),"symbol_h2h":str(OUT_SYMBOL),"monthly_h2h":str(OUT_MONTH)
 },
 "governance":{
    "v4_semantic_status":"RESEARCH_CERTIFIED_WITH_DOCUMENTED_SOURCE_LIMITATION",
    "full_24case_tradingview_parity":False,
    "v4_modified":False,"v5_modified":False,
    "common_evidence_source_changed":False,
    "production_rule_authorized":False
 }
}
OUT_SUMMARY.write_text(json.dumps(summary,indent=2),encoding="utf-8")

print("\n=== FINAL 9N HEAD-TO-HEAD ===")
print("V4 =",overall["v4"])
print("V5 =",overall["v5"])
print("V5_MINUS_V4_RATE =",point)
print("BOOTSTRAP_95CI =",float(lo),float(hi))
print("CLASSIFICATION =",winner)
print("FRACTION_SYMBOLS_V5_GT_V4 =",frac_symbols_v5_gt_v4)
print("SUMMARY =",OUT_SUMMARY)
print("SYMBOL =",OUT_SYMBOL)
print("MONTHLY =",OUT_MONTH)
print("V4_EVENTS =",OUT_V4)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_3S_FINAL_H2H=PASS")
