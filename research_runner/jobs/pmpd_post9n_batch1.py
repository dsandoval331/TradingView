from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

SEED=9102026
REPS=5000
START=pd.Timestamp("2026-01-05").date()
END=pd.Timestamp("2026-09-02").date()


def _outcome(s):
    return s.astype(str).str.upper().str.strip().replace({"BOTH":"AMBIGUOUS_SAME_BAR","NEITHER":"UNRESOLVED"})


def _stats(df):
    o=_outcome(df.outcome); f=int((o=="FAVORABLE_FIRST").sum()); a=int((o=="ADVERSE_FIRST").sum()); r=f+a
    return f,a,r,(f/r if r else np.nan)


def _boot(df, mask, base_rate, reps=REPS):
    syms=sorted(df.symbol.unique()); rng=np.random.default_rng(SEED); vals=[]
    for _ in range(reps):
        sampled=rng.choice(syms,len(syms),replace=True); f=a=0
        for sym in sampled:
            g=df[(df.symbol==sym) & mask]
            o=_outcome(g.outcome); f+=int((o=="FAVORABLE_FIRST").sum()); a+=int((o=="ADVERSE_FIRST").sum())
        if f+a: vals.append(f/(f+a)-base_rate)
    return tuple(map(float,np.quantile(vals,[.025,.5,.975]))) if vals else (np.nan,np.nan,np.nan)


def run(root: Path) -> dict:
    v5p=root/"pmpd_v5_9m_oos_candidate_dp4_v1.parquet"
    cache=root/"data"/"second1m_alt_entry_cache_v1"/"partitions"
    if not v5p.exists(): raise FileNotFoundError(v5p)
    out=root/"research_outputs"/"pmpd"/"post9n_batch1"; out.mkdir(parents=True,exist_ok=True)
    v=pd.read_parquet(v5p).copy(); v["trade_date"]=pd.to_datetime(v.trade_date).dt.date
    v=v[v.trade_date.between(START,END)].copy(); v["outcome"]=_outcome(v.outcome)
    v["timestamp_utc"]=pd.to_datetime(v.timestamp_utc,utc=True); v["timestamp_et"]=v.timestamp_utc.dt.tz_convert("America/New_York")
    v["gap_aligned"]=np.where(v.direction.str.upper().eq("BULL"),v.overnight_gap_pct>0,v.overnight_gap_pct<0)
    v["gap_abs"]=v.overnight_gap_pct.abs(); v["event_minute"]=v.timestamp_et.dt.hour*60+v.timestamp_et.dt.minute
    v["time_bucket"]=pd.cut(v.event_minute,[569,629,689,749,809,869,929,989,2000],labels=["09:30-10:29","10:30-11:29","11:30-12:29","12:30-13:29","13:30-14:29","14:30-15:29","15:30-16:29","16:30+"])
    for c in ["gap_abs","six_level_scale_ratio","stack_width_pct_geometry"]:
        if c in v: v[c+"_quartile"]=pd.qcut(v[c],4,duplicates="drop")
    _,_,base_res,base_rate=_stats(v)

    def load(sym):
        p=cache/sym/f"{sym}_2026.parquet"
        if not p.exists(): return None
        d=pd.read_parquet(p).copy(); d["timestamp_utc"]=pd.to_datetime(d.timestamp_utc,utc=True); d["timestamp_et"]=d.timestamp_utc.dt.tz_convert("America/New_York"); d["trade_date"]=d.timestamp_et.dt.date
        return d

    bench={s:load(s) for s in ["SPY","QQQ"]}; bench={k:d for k,d in bench.items() if d is not None}
    def bret(sym,date,ts):
        d=bench.get(sym)
        if d is None:return np.nan
        g=d[(d.trade_date==date)&(d.timestamp_et.dt.time>=pd.Timestamp("09:30").time())&(d.timestamp_et<=ts)]
        return float(g.iloc[-1].close/g.iloc[0].open-1) if len(g) else np.nan
    sign=np.where(v.direction.str.upper().eq("BULL"),1,-1)
    for sym in bench:
        col=sym.lower()+"_ret_to_event"; v[col]=[bret(sym,d,t) for d,t in zip(v.trade_date,v.timestamp_et)]; v[sym.lower()+"_aligned"]=(v[col]*sign)>0
    if {"spy_aligned","qqq_aligned"}.issubset(v.columns): v["market_both_aligned"]=v.spy_aligned&v.qqq_aligned

    v["opening_rvol_5m"]=np.nan; v["eventbar_rvol_5m"]=np.nan
    volume_col=None
    sample=next(iter(cache.glob("*/*_2026.parquet")),None)
    if sample:
        cols=pd.read_parquet(sample).columns
        volume_col=next((c for c in ["volume","v","Volume"] if c in cols),None)
    if volume_col:
        for n,sym in enumerate(sorted(v.symbol.unique()),1):
            print(f"[{n}/{v.symbol.nunique()}] CONTEXT {sym}")
            d=load(sym)
            if d is None:continue
            r=d[(d.timestamp_et.dt.time>=pd.Timestamp("09:30").time())&(d.timestamp_et.dt.time<=pd.Timestamp("15:59").time())].copy()
            if r.empty:continue
            r["bar5"]=r.timestamp_et.dt.floor("5min")
            bars=r.groupby(["trade_date","bar5"],as_index=False).agg(vol=(volume_col,"sum")); bars["clock"]=bars.bar5.dt.strftime("%H:%M")
            dates=sorted(bars.trade_date.unique()); hist={}
            for date in dates:
                prior=[x for x in dates if x<date][-20:]
                for row in bars[bars.trade_date==date].itertuples():
                    h=bars[bars.trade_date.isin(prior)&(bars.clock==row.clock)].vol; med=float(h.median()) if len(h)>=5 else np.nan
                    hist[(date,row.clock)]=float(row.vol)/med if med and med>0 else np.nan
            idx=v.symbol==sym; clocks=v.loc[idx,"timestamp_et"].dt.floor("5min").dt.strftime("%H:%M")
            v.loc[idx,"opening_rvol_5m"]=[hist.get((d,"09:30"),np.nan) for d in v.loc[idx,"trade_date"]]
            v.loc[idx,"eventbar_rvol_5m"]=[hist.get((d,c),np.nan) for d,c in zip(v.loc[idx,"trade_date"],clocks)]

    rows=[]
    def test(name,mask,family):
        mask=mask.fillna(False); g=v[mask]; f,a,r,rate=_stats(g)
        if not r:return
        lo,med,hi=_boot(v,mask,base_rate)
        rows.append(dict(family=family,test=name,events=len(g),resolved=r,favorable_first=f,adverse_first=a,resolved_favorable_rate=rate,lift_vs_all=rate-base_rate,ci95_lower=lo,bootstrap_median=med,ci95_upper=hi))
    test("gap_aligned",v.gap_aligned,"gap")
    for c,fam in [("gap_abs_quartile","gap"),("six_level_scale_ratio_quartile","geometry"),("stack_width_pct_geometry_quartile","geometry")]:
        if c in v:
            for q in v[c].dropna().unique():test(f"{c}_{q}",v[c]==q,fam)
    for q in v.time_bucket.dropna().unique():test(f"time_{q}",v.time_bucket==q,"time")
    for col,fam in [("opening_rvol_5m","rvol"),("eventbar_rvol_5m","rvol")]:
        if v[col].notna().any():
            for th in [1,1.5,2,3]:test(f"{col}_ge_{th}",v[col]>=th,fam)
    for c in ["spy_aligned","qqq_aligned","market_both_aligned"]:
        if c in v:test(c,v[c],"market")
    factors=pd.DataFrame(rows).sort_values(["ci95_lower","lift_vs_all"],ascending=False); factors.to_csv(out/"factor_results.csv",index=False)

    combos=[]
    def combo(name,mask):
        mask=mask.fillna(False); g=v[mask]; f,a,r,rate=_stats(g)
        if r<100:return
        lo,med,hi=_boot(v,mask,base_rate); combos.append(dict(combo=name,events=len(g),resolved=r,rate=rate,lift_vs_all=rate-base_rate,ci95_lower=lo,bootstrap_median=med,ci95_upper=hi))
    if v.opening_rvol_5m.notna().any():
        hi=v.opening_rvol_5m>=1.5; combo("gap_aligned + opening_rvol>=1.5",v.gap_aligned&hi)
        if "market_both_aligned" in v: combo("gap + opening_rvol>=1.5 + market",v.gap_aligned&hi&v.market_both_aligned); combo("opening_rvol>=1.5 + market",hi&v.market_both_aligned)
    if v.eventbar_rvol_5m.notna().any():combo("gap_aligned + eventbar_rvol>=1.5",v.gap_aligned&(v.eventbar_rvol_5m>=1.5))
    if "market_both_aligned" in v:combo("gap_aligned + market",v.gap_aligned&v.market_both_aligned)
    cdf=pd.DataFrame(combos)
    if not cdf.empty:cdf=cdf.sort_values(["ci95_lower","lift_vs_all"],ascending=False)
    cdf.to_csv(out/"combo_results.csv",index=False); v.to_parquet(out/"context_enriched.parquet",index=False)
    summary={"step":"PMPD-POST9N-B1","baseline":{"events":len(v),"resolved":base_res,"resolved_favorable_rate":base_rate},"volume_column":volume_col,"benchmarks":sorted(bench),"factor_tests":len(factors),"combo_tests":len(cdf),"top_factors":factors.head(15).to_dict("records"),"top_combos":cdf.head(15).to_dict("records") if len(cdf) else [],"governance":{"v5_modified":False,"h2h_modified":False,"production_rule_authorized":False,"research_only":True}}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")
    print("OUTPUT_DIR=",out); print("BASELINE_RATE=",base_rate)
    return {"output_dir":str(out),"summary":str(out/"summary.json"),"factor_results":str(out/"factor_results.csv"),"combo_results":str(out/"combo_results.csv")}
