from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
PRED = ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet"
SESS = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
ROB = ROOT / "ae2_robustness_v1" / "ae2_robustness_features_v1.parquet"
OUTDIR = ROOT / "ae2_c1_c2_transition_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a39_vwap_q3_exhaustion_independence_v1.csv"
BINARY = {"FAVORABLE_FIRST","ADVERSE_FIRST"}

def stats(x):
    x=x[x["outcome"].isin(BINARY)]
    n=len(x); fav=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, 100.0*fav/n if n else np.nan

def interval_left(v):
    return v.left if hasattr(v,"left") else float("-inf")

def main():
    pred=pd.read_parquet(PRED)
    sess=pd.read_parquet(SESS)
    rob=pd.read_parquet(ROB)

    for d in (pred,sess,rob):
        if "trade_date" in d.columns:
            d["trade_date"]=pd.to_datetime(d["trade_date"])

    preferred=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    keys=[k for k in preferred if k in pred.columns and k in sess.columns and k in rob.columns]
    if len(keys)<3:
        raise RuntimeError(f"Insufficient shared event keys: {keys}")

    sess_need=keys+["session_level_clear_state","market_prior_5d_consensus","research_period"]
    s=sess[sess_need].drop_duplicates(keys)

    # Locate frozen exhaustion state without inventing/recomputing it.
    exhaustion_candidates=[
        "exhaustion_state",
        "exhaustion_extreme_count_state",
        "exhaustion_extreme_count",
    ]
    excol=next((c for c in exhaustion_candidates if c in rob.columns),None)
    if excol is None:
        matches=[c for c in rob.columns if "exhaust" in c.lower()]
        raise KeyError(f"No frozen exhaustion state found. Exhaustion-like columns: {matches}")

    r=rob[keys+[excol]].drop_duplicates(keys)

    p=pred.drop(columns=[c for c in [
        "session_level_clear_state","market_prior_5d_consensus","research_period",excol
    ] if c in pred.columns],errors="ignore")

    x=p.merge(s,on=keys,how="left",validate="one_to_one")
    x=x.merge(r,on=keys,how="left",validate="one_to_one")

    if len(x)!=len(pred):
        raise RuntimeError("Row-count parity failed after enrichment.")
    if x[["session_level_clear_state","market_prior_5d_consensus","research_period",excol]].isna().any(axis=1).any():
        raise RuntimeError("Missing enrichment fields after join.")

    x=x[
        x["outcome"].isin(BINARY)
        & x["session_level_clear_state"].eq("ALL_3_CLEARED")
        & x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ].copy()

    b="vwap_distance_change_pp__bucket"
    cats=sorted(list(x[b].dropna().unique()),key=interval_left)
    rank={c:i+1 for i,c in enumerate(cats)}
    x["vwap_q"]=x[b].map(rank).astype("Int64")
    x["A39_VWAP_Q3"]=x["vwap_q"].eq(3)

    print("="*120)
    print("A39.5 - VWAP-DISTANCE Q3 vs FROZEN EXHAUSTION INDEPENDENCE AUDIT")
    print("="*120)
    print(f"Frozen exhaustion source: {ROB}")
    print(f"Frozen exhaustion column: {excol}")
    print(f"Historical Preferred binary events: {len(x):,}")
    print("\nFrozen exhaustion value counts:")
    print(x[excol].value_counts(dropna=False).to_string())

    rows=[]
    for period in ["DISCOVERY","VALIDATION"]:
        pset=x[x["research_period"].eq(period)]
        bn,br=stats(pset)
        hit=pset[pset["A39_VWAP_Q3"]]
        hn,hr=stats(hit)
        rows.append([period,"POOLED","ALL",hn,hr,bn,br,hr-br])

        for state,base in pset.groupby(excol,dropna=False):
            sn,sr=stats(base)
            h=base[base["A39_VWAP_Q3"]]
            n,rp=stats(h)
            rows.append([period,"EXHAUSTION_STATE",str(state),n,rp,sn,sr,rp-sr if n else np.nan])

        # Explicitly test Q3 after excluding any non-NONE exhaustion if categorical state supports it.
        vals=set(pset[excol].astype(str).unique())
        if "NONE" in vals:
            base=pset[pset[excol].astype(str).eq("NONE")]
            sn,sr=stats(base); h=base[base["A39_VWAP_Q3"]]; n,rp=stats(h)
            rows.append([period,"EXHAUSTION_NONE_ONLY","NONE",n,rp,sn,sr,rp-sr if n else np.nan])

    out=pd.DataFrame(rows,columns=[
        "research_period","split_type","split_value","candidate_n","candidate_ff_pct",
        "conditional_baseline_n","conditional_baseline_ff_pct","incremental_lift_pp"
    ])
    out.to_csv(OUT,index=False)

    print("\nINDEPENDENCE RESULTS")
    print("-"*120)
    print(out.to_string(index=False,float_format=lambda v:f"{v:.2f}"))
    print(f"\nFull output: {OUT}")
    print("RESULT: EXHAUSTION INDEPENDENCE AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
