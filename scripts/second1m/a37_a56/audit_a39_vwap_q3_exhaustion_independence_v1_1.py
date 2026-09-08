from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
PRED = ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet"
SESS = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
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

def find_exhaustion_source():
    preferred = [
        ROOT / "ae2_trend_exhaustion_robustness_v1",
        ROOT / "ae2_robustness_v1",
    ]
    hits=[]
    for d in preferred:
        if d.exists():
            hits += sorted(d.glob("*.parquet"))
    hits += sorted(ROOT.rglob("*exhaust*.parquet"))
    hits += sorted(ROOT.rglob("*robustness*.parquet"))

    seen=set()
    for p in hits:
        if p in seen or not p.exists():
            continue
        seen.add(p)
        try:
            cols=pd.read_parquet(p).columns.tolist()
        except Exception:
            continue
        ex=[c for c in cols if "exhaust" in c.lower()]
        if ex:
            return p, ex
    return None, []

def main():
    rob_path, excols = find_exhaustion_source()
    if rob_path is None:
        print("="*120)
        print("A39.5 V1.1 - EXHAUSTION SOURCE DISCOVERY")
        print("="*120)
        print("Could not locate a parquet containing a frozen exhaustion field.")
        print("\nParquet files with 'robust' or 'exhaust' in path:")
        for p in sorted(set(ROOT.rglob("*.parquet"))):
            s=str(p).lower()
            if "robust" in s or "exhaust" in s:
                print(p)
        print("\nSTOP: no research conclusions generated.")
        return

    pred=pd.read_parquet(PRED)
    sess=pd.read_parquet(SESS)
    rob=pd.read_parquet(rob_path)
    for d in (pred,sess,rob):
        if "trade_date" in d.columns:
            d["trade_date"]=pd.to_datetime(d["trade_date"])

    preferred=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    keys=[k for k in preferred if k in pred.columns and k in sess.columns and k in rob.columns]
    if len(keys)<3:
        raise RuntimeError(f"Insufficient shared event keys: {keys}")

    # Prefer categorical frozen state; otherwise count is acceptable without recomputation.
    priority=["exhaustion_state","exhaustion_extreme_count_state","exhaustion_extreme_count"]
    excol=next((c for c in priority if c in rob.columns), excols[0])

    s=sess[keys+["session_level_clear_state","market_prior_5d_consensus","research_period"]].drop_duplicates(keys)
    r=rob[keys+[excol]].drop_duplicates(keys)
    p=pred.drop(columns=[c for c in [
        "session_level_clear_state","market_prior_5d_consensus","research_period",excol
    ] if c in pred.columns],errors="ignore")

    x=p.merge(s,on=keys,how="left",validate="one_to_one")
    x=x.merge(r,on=keys,how="left",validate="one_to_one")

    print("="*120)
    print("A39.5 V1.1 - VWAP Q3 vs FROZEN EXHAUSTION INDEPENDENCE AUDIT")
    print("="*120)
    print(f"Discovered frozen exhaustion source: {rob_path}")
    print(f"Frozen exhaustion column: {excol}")
    print(f"Join keys: {keys}")
    print(f"Predictor rows: {len(pred):,}")
    print(f"Joined rows: {len(x):,}")

    if len(x)!=len(pred):
        raise RuntimeError("Row-count parity failed after enrichment.")

    required=["session_level_clear_state","market_prior_5d_consensus","research_period",excol]
    missing=int(x[required].isna().any(axis=1).sum())
    print(f"Rows missing required enrichment: {missing:,}")
    if missing:
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

    print(f"Historical Preferred binary events: {len(x):,}")
    print("\nFrozen exhaustion value counts:")
    print(x[excol].value_counts(dropna=False).to_string())

    rows=[]
    for period in ["DISCOVERY","VALIDATION"]:
        pset=x[x["research_period"].eq(period)]
        bn,br=stats(pset); h=pset[pset["A39_VWAP_Q3"]]; n,rp=stats(h)
        rows.append([period,"POOLED","ALL",n,rp,bn,br,rp-br])

        for state,base in pset.groupby(excol,dropna=False):
            sn,sr=stats(base); h=base[base["A39_VWAP_Q3"]]; n,rp=stats(h)
            rows.append([period,"EXHAUSTION_STATE",str(state),n,rp,sn,sr,rp-sr if n else np.nan])

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
