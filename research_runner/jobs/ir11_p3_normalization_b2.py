from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

P1=Path("research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet")
PAIR=Path("research_outputs/ir11/p2/ir11_p2_pairwise_outcomes_2025_v1.parquet")
OUT=Path("research_outputs/ir11/p3")
EXPECTED=(149546,3738650,104,250)
PAIRS=[(0.50,0.25),(0.50,0.50),(0.75,0.50),(1.00,0.50)]

def qbin(s,edges,labels): return pd.cut(s,edges,labels=labels,include_lowest=True,right=False)

def summarize(x,method,bucket):
    z=x.copy(); z["method"]=method; z["bucket"]=bucket.astype(str)
    z["fav"]=z.first_passage_outcome.eq("FAVORABLE_FIRST"); z["adv"]=z.first_passage_outcome.eq("ADVERSE_FIRST"); z["amb"]=z.first_passage_outcome.eq("AMBIGUOUS_SAME_BAR"); z["resolved"]=z.fav|z.adv
    g=z.groupby(["favorable_threshold_pct","adverse_threshold_pct","clock","method","bucket"],dropna=False).agg(n=("symbol","size"),symbols=("symbol","nunique"),dates=("trade_date","nunique"),favorable_first=("fav","sum"),adverse_first=("adv","sum"),ambiguous=("amb","sum"),resolved=("resolved","sum")).reset_index()
    g["favorable_pct_all"]=100*g.favorable_first/g.n; g["favorable_pct_resolved"]=100*g.favorable_first/g.resolved.replace(0,np.nan); g["ambiguous_pct"]=100*g.ambiguous/g.n
    return g

def run(work_root:Path)->dict:
    root=Path(work_root).resolve(); out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    p1=pd.read_parquet(root/P1); pairs=pd.read_parquet(root/PAIR)
    gate=(len(p1),len(pairs),p1.symbol.nunique(),pd.to_datetime(p1.trade_date).dt.date.nunique())
    if gate!=EXPECTED: raise RuntimeError(f"P3-B2 parity gate failed {gate} != {EXPECTED}")
    p1=p1.copy(); p1["trade_date"]=pd.to_datetime(p1.trade_date)
    # Reconstruct same-symbol/same-clock prior-60 normalization strictly from P1 displacement history.
    p1=p1.sort_values(["symbol","clock","trade_date"])
    grp=p1.groupby(["symbol","clock"],sort=False)["displacement_pct"]
    p1["roll60_n"]=grp.transform(lambda s:s.shift(1).rolling(60,min_periods=60).count())
    p1["roll60_mean"]=grp.transform(lambda s:s.shift(1).rolling(60,min_periods=60).mean())
    p1["roll60_std"]=grp.transform(lambda s:s.shift(1).rolling(60,min_periods=60).std(ddof=1))
    p1["roll60_z"]=(p1.displacement_pct-p1.roll60_mean)/p1.roll60_std.replace(0,np.nan)
    def prior_pct(s):
        vals=s.to_numpy(dtype=float); out=np.full(len(vals),np.nan)
        for i in range(60,len(vals)):
            hist=vals[i-60:i]
            if np.isfinite(vals[i]) and np.isfinite(hist).sum()==60:
                out[i]=np.mean(hist<=vals[i])
        return pd.Series(out,index=s.index)
    p1["roll60_pct"]=grp.apply(prior_pct).reset_index(level=[0,1],drop=True)
    norm=p1[["symbol","trade_date","clock","roll60_n","roll60_pct","roll60_z"]]
    w=pairs[pairs.apply(lambda r:(float(r.favorable_threshold_pct),float(r.adverse_threshold_pct)) in PAIRS,axis=1)].copy()
    w["trade_date"]=pd.to_datetime(w.trade_date); w=w.merge(norm,on=["symbol","trade_date","clock"],how="left",validate="many_to_one")
    parts=[]
    parts.append(summarize(w,"RAW_PCT",qbin(w.displacement_pct,[-np.inf,0,.5,1,2,3,5,np.inf],["NEG","0-.5",".5-1","1-2","2-3","3-5",">=5"])))
    eligible=w.roll60_n.eq(60)
    parts.append(summarize(w[eligible],"SAME_CLOCK_ROLL60_PERCENTILE",qbin(w.loc[eligible,"roll60_pct"],[-np.inf,.5,.75,.9,.95,.975,.99,np.inf],["<50","50-75","75-90","90-95","95-97.5","97.5-99",">=99"])))
    zel=eligible&w.roll60_z.notna()
    parts.append(summarize(w[zel],"SAME_CLOCK_ROLL60_Z",qbin(w.loc[zel,"roll60_z"],[-np.inf,0,.5,1,1.5,2,3,np.inf],["<0","0-.5",".5-1","1-1.5","1.5-2","2-3",">=3"])))
    w["cs_n"]=w.groupby(["favorable_threshold_pct","adverse_threshold_pct","trade_date","clock"]).symbol.transform("nunique")
    w["cs_rank"]=w.groupby(["favorable_threshold_pct","adverse_threshold_pct","trade_date","clock"]).displacement_pct.rank(pct=True)
    cs=w[w.cs_n>=80].copy()
    parts.append(summarize(cs,"CROSS_SECTIONAL_RANK_MIN80",qbin(cs.cs_rank,[-np.inf,.5,.75,.9,.95,.975,.99,np.inf],["<50","50-75","75-90","90-95","95-97.5","97.5-99",">=99"])))
    summary=pd.concat(parts,ignore_index=True)
    sp=out/"ir11_p3_normalization_b2_summary.csv"; summary.to_csv(sp,index=False)
    manifest=pd.DataFrame([{"p1_rows":len(p1),"pair_rows":len(pairs),"analysis_rows":len(w),"symbols":w.symbol.nunique(),"dates":w.trade_date.dt.date.nunique(),"pairs":";".join(f"{a:.2f}/{b:.2f}" for a,b in PAIRS),"methods":";".join(summary.method.unique()),"roll60_ready_rows":int(p1.roll60_n.eq(60).sum()),"note":"Broad pre-specified bins. Rolling percentile/z reconstructed strictly from prior 60 same-symbol same-clock P1 displacement observations. No ATR claim in B2; prior-information ATR deferred until source derivation is independently certified. Descriptive only; no execution qualification; frozen 104-symbol population unchanged."}])
    mp=out/"ir11_p3_normalization_b2_manifest.csv"; manifest.to_csv(mp,index=False)
    return {"artifact":str(sp),"output_paths":[str(sp),str(mp)],"research_phase":"IR11-P3","batch":"P3-B2","research_logic_modified":False}
