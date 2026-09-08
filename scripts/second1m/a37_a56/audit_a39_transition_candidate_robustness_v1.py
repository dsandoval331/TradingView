from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
TRANS = ROOT / "ae2_c1_c2_transition_v1"
PERF = TRANS / "a39_transition_frozen_quintile_performance_v1.csv"
DIR = TRANS / "a39_transition_frozen_quintile_direction_v1.csv"

# Original enriched source for quarter/date stress.
PRED = ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet"
SESS = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"

OUT = TRANS / "a39_transition_candidate_robustness_v1.csv"
BINARY = {"FAVORABLE_FIRST","ADVERSE_FIRST"}

# Predeclared promotion screen:
# Require same sign in discovery/validation and >=3pp vs Preferred baseline in BOTH.
CANDIDATES = [
    ("vwap_distance_change_pp", 3, "POSITIVE"),
]

def ff_stats(x):
    x = x[x["outcome"].isin(BINARY)]
    n = len(x)
    fav = int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, 100.0*fav/n if n else np.nan

def interval_left(v):
    return v.left if hasattr(v, "left") else float("-inf")

def main():
    pred = pd.read_parquet(PRED)
    sess = pd.read_parquet(SESS)
    for d in (pred,sess):
        d["trade_date"] = pd.to_datetime(d["trade_date"])

    keys = [k for k in [
        "symbol","trade_date","direction","architecture",
        "decision_candle","entry_timestamp"
    ] if k in pred.columns and k in sess.columns]

    need = keys + [
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "research_period",
    ]
    s = sess[need].drop_duplicates(keys)
    p = pred.drop(columns=[c for c in [
        "session_level_clear_state","market_prior_5d_consensus","research_period"
    ] if c in pred.columns], errors="ignore")
    x = p.merge(s,on=keys,how="left",validate="one_to_one")
    x = x[
        x["outcome"].isin(BINARY)
        & x["session_level_clear_state"].eq("ALL_3_CLEARED")
        & x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ].copy()
    x["quarter"] = x["trade_date"].dt.to_period("Q").astype(str)

    rows = []
    for feature, quintile, sign in CANDIDATES:
        bucket = feature + "__bucket"
        cats = sorted(list(x[bucket].dropna().unique()), key=interval_left)
        rank = {c:i+1 for i,c in enumerate(cats)}
        qcol = feature + "__frozen_quintile"
        x[qcol] = x[bucket].map(rank).astype("Int64")
        mask = x[qcol].eq(quintile)

        for period in ["DISCOVERY","VALIDATION"]:
            pset = x[x["research_period"].eq(period)]
            bn,br = ff_stats(pset)
            hit = pset[mask.loc[pset.index]]
            n,r = ff_stats(hit)
            rows.append({
                "candidate":f"{feature}_Q{quintile}",
                "expected_sign":sign,
                "split_type":"POOLED",
                "split_value":period,
                "candidate_n":n,
                "candidate_ff_pct":r,
                "baseline_n":bn,
                "baseline_ff_pct":br,
                "lift_pp":r-br if n else np.nan,
            })

            for direction,dset in pset.groupby("direction"):
                dbn,dbr = ff_stats(dset)
                dhit = dset[mask.loc[dset.index]]
                dn,dr = ff_stats(dhit)
                rows.append({
                    "candidate":f"{feature}_Q{quintile}",
                    "expected_sign":sign,
                    "split_type":"DIRECTION",
                    "split_value":f"{period}:{direction}",
                    "candidate_n":dn,
                    "candidate_ff_pct":dr,
                    "baseline_n":dbn,
                    "baseline_ff_pct":dbr,
                    "lift_pp":dr-dbr if dn else np.nan,
                })

        for quarter,qset in x.groupby("quarter"):
            qn,qr = ff_stats(qset)
            qhit = qset[mask.loc[qset.index]]
            n,r = ff_stats(qhit)
            if n >= 8:
                rows.append({
                    "candidate":f"{feature}_Q{quintile}",
                    "expected_sign":sign,
                    "split_type":"QUARTER",
                    "split_value":quarter,
                    "candidate_n":n,
                    "candidate_ff_pct":r,
                    "baseline_n":qn,
                    "baseline_ff_pct":qr,
                    "lift_pp":r-qr,
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT,index=False)

    print("="*116)
    print("A39.4 - TRANSITION CANDIDATE ROBUSTNESS AUDIT")
    print("="*116)
    print("Promotion screen used: same sign + >=3pp vs Preferred baseline in BOTH discovery and validation.")
    print("Only one A39 cell qualified that gate: VWAP-distance-change frozen Q3 (positive).")

    for split in ["POOLED","DIRECTION","QUARTER"]:
        print("\n"+split)
        print("-"*116)
        z=out[out["split_type"].eq(split)]
        print(z.to_string(index=False,float_format=lambda v:f"{v:.2f}") if len(z) else "NONE")

    print(f"\nFull output: {OUT}")
    print("RESULT: A39 TRANSITION ROBUSTNESS AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
