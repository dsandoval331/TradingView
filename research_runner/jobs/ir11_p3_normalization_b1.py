from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

P1=Path("research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet")
PAIR=Path("research_outputs/ir11/p2/ir11_p2_pairwise_outcomes_2025_v1.parquet")
OUT=Path("research_outputs/ir11/p3")
EXPECTED=(149546,3738650,104,250)
PRIMARY=(0.50,0.50)

def qbin(s, edges, labels):
    return pd.cut(s, edges, labels=labels, include_lowest=True, right=False)

def summarize(w, method, bucket):
    x=w.copy(); x["method"]=method; x["bucket"]=bucket.astype(str)
    x["fav"]=x.first_passage_outcome.eq("FAVORABLE_FIRST")
    x["adv"]=x.first_passage_outcome.eq("ADVERSE_FIRST")
    x["amb"]=x.first_passage_outcome.eq("AMBIGUOUS_SAME_BAR")
    x["resolved"]=x.fav|x.adv
    g=x.groupby(["clock","method","bucket"],dropna=False).agg(
      n=("symbol","size"),symbols=("symbol","nunique"),dates=("trade_date","nunique"),
      favorable_first=("fav","sum"),adverse_first=("adv","sum"),ambiguous=("amb","sum"),resolved=("resolved","sum")).reset_index()
    g["favorable_pct_all"]=100*g.favorable_first/g.n
    g["favorable_pct_resolved"]=100*g.favorable_first/g.resolved.replace(0,np.nan)
    g["ambiguous_pct"]=100*g.ambiguous/g.n
    return g

def run(work_root:Path)->dict:
    root=Path(work_root).resolve(); out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    p1=pd.read_parquet(root/P1); pairs=pd.read_parquet(root/PAIR)
    gate=(len(p1),len(pairs),p1.symbol.nunique(),pd.to_datetime(p1.trade_date).dt.date.nunique())
    if gate!=EXPECTED: raise RuntimeError(f"P3 parity gate failed {gate} != {EXPECTED}")
    w=pairs[(pairs.favorable_threshold_pct==PRIMARY[0])&(pairs.adverse_threshold_pct==PRIMARY[1])].copy()
    # Join P1-only normalization fields defensively by stable observation keys where available.
    keys=[k for k in ["symbol","trade_date","clock"] if k in p1.columns and k in w.columns]
    cols=keys+[c for c in ["atr14_prior","displacement_atr","relative_percentile_trailing60","relative_z_trailing60"] if c in p1.columns]
    if len(cols)>len(keys):
        norm=p1[cols].drop_duplicates(keys)
        w=w.merge(norm,on=keys,how="left",suffixes=("","_p1"))
    outputs=[]
    parts=[]
    raw=qbin(w.displacement_pct,[-np.inf,0,.5,1,2,3,5,np.inf],["NEG","0-.5",".5-1","1-2","2-3","3-5",">=5"])
    parts.append(summarize(w,"RAW_PCT",raw))
    atrcol=next((c for c in ["displacement_atr","displacement_atr_p1"] if c in w.columns),None)
    if atrcol:
        atr=qbin(w[atrcol],[-np.inf,0,.25,.5,.75,1,1.5,2,np.inf],["NEG","0-.25",".25-.5",".5-.75",".75-1","1-1.5","1.5-2",">=2"])
        parts.append(summarize(w,"PRIOR_ATR",atr))
    pctcol=next((c for c in ["relative_percentile_trailing60","relative_percentile_trailing60_p1"] if c in w.columns),None)
    if pctcol:
        s=w[pctcol].astype(float); s=s/100 if s.dropna().median()>1 else s
        rb=qbin(s,[-np.inf,.5,.75,.9,.95,.975,.99,np.inf],["<50","50-75","75-90","90-95","95-97.5","97.5-99",">=99"])
        parts.append(summarize(w,"SAME_CLOCK_ROLL60_PERCENTILE",rb))
    zcol=next((c for c in ["relative_z_trailing60","relative_z_trailing60_p1"] if c in w.columns),None)
    if zcol:
        zb=qbin(w[zcol],[-np.inf,0,.5,1,1.5,2,3,np.inf],["<0","0-.5",".5-1","1-1.5","1.5-2","2-3",">=3"])
        parts.append(summarize(w,"SAME_CLOCK_ROLL60_Z",zb))
    # Cross-sectional rank is descriptive only and only on dates/clocks with >=80 symbols.
    w["cs_n"]=w.groupby(["trade_date","clock"]).symbol.transform("nunique")
    w["cs_rank"]=w.groupby(["trade_date","clock"]).displacement_pct.rank(pct=True)
    cs=w[w.cs_n>=80].copy()
    if len(cs):
        cb=qbin(cs.cs_rank,[-np.inf,.5,.75,.9,.95,.975,.99,np.inf],["<50","50-75","75-90","90-95","95-97.5","97.5-99",">=99"])
        parts.append(summarize(cs,"CROSS_SECTIONAL_RANK_MIN80",cb))
    summary=pd.concat(parts,ignore_index=True)
    p=out/"ir11_p3_normalization_b1_summary.csv"; summary.to_csv(p,index=False); outputs.append(str(p))
    manifest=pd.DataFrame([{"p1_rows":len(p1),"pair_rows":len(pairs),"analysis_rows":len(w),"symbols":w.symbol.nunique(),"dates":pd.to_datetime(w.trade_date).dt.date.nunique(),"pair":"0.50/0.50","methods":";".join(summary.method.unique()),"cross_sectional_min_symbols":80,"note":"Broad pre-specified normalization bins; descriptive research only; no execution qualification; certified P1/P2 population unchanged."}])
    p2=out/"ir11_p3_normalization_b1_manifest.csv"; manifest.to_csv(p2,index=False); outputs.append(str(p2))
    return {"artifact":outputs[0],"output_paths":outputs,"research_phase":"IR11-P3","batch":"P3-B1","research_logic_modified":False}
