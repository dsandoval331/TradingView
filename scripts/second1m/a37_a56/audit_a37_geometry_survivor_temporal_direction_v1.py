from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1/ae2_session_level_geometry_v1")
EVENTS = ROOT / "a37_session_level_geometry_events_v1.parquet"
THRESH = ROOT / "a37_geometry_discovery_quintile_thresholds_v1.csv"
OUT = ROOT / "a37_geometry_survivor_temporal_direction_audit_v1.csv"

BINARY = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}

# Collapsed/independent survivors from A37.12.
CANDIDATES = {
    "N_PM_PD_Q4": ("pm_pd_spacing_pct", "Q4"),
    "N_OUTER_PEN_Q4": ("c2_beyond_outermost_pct", "Q4"),
    "P_COMPACT_GEOMETRY_Q2": ("mean_pairwise_spacing_pct", "Q2"),
    "P_ORDER_PD_AH_PM": ("directional_level_order_inner_to_outer", "PD>AH>PM"),
}

def stats(x):
    x = x[x["outcome"].isin(BINARY)]
    n = len(x)
    fav = int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, fav, 100.0 * fav / n if n else np.nan

def qmaps():
    t = pd.read_csv(THRESH)
    out = {}
    for metric, g in t.groupby("metric"):
        m = dict(zip(g["cutpoint"], g["value"]))
        if all(k in m for k in ("q20","q40","q60","q80")):
            out[metric] = [-np.inf,m["q20"],m["q40"],m["q60"],m["q80"],np.inf]
    return out

def mask_for(e, feature, state, qm):
    if state.startswith("Q"):
        return pd.cut(pd.to_numeric(e[feature], errors="coerce"),
                      qm[feature], labels=["Q1","Q2","Q3","Q4","Q5"],
                      include_lowest=True).astype("object").eq(state)
    return e[feature].astype(str).eq(state)

def main():
    e = pd.read_parquet(EVENTS)
    e = e[e["preferred_family"] & e["outcome"].isin(BINARY)].copy()
    e["trade_date"] = pd.to_datetime(e["trade_date"])
    e["quarter"] = e["trade_date"].dt.to_period("Q").astype(str)
    qm = qmaps()
    masks = {k: mask_for(e,*v,qm) for k,v in CANDIDATES.items()}

    rows=[]
    for cand, mask in masks.items():
        # quarter, direction, and quarter x direction
        specs = [
            ("QUARTER", ["quarter"]),
            ("DIRECTION", ["direction"]),
            ("QUARTER_DIRECTION", ["quarter","direction"]),
        ]
        for split_type, cols in specs:
            for keys, idx in e.groupby(cols, dropna=False).groups.items():
                if not isinstance(keys, tuple): keys=(keys,)
                base=e.loc[idx]
                hit=e.loc[idx][mask.loc[idx]]
                bn,bf,br=stats(base); hn,hf,hr=stats(hit)
                if hn < 8:
                    continue
                row={
                    "candidate":cand,"split_type":split_type,
                    "baseline_n":bn,"baseline_ff_pct":br,
                    "candidate_n":hn,"candidate_ff_pct":hr,
                    "lift_pp":hr-br
                }
                row.update(dict(zip(cols,keys)))
                rows.append(row)

    out=pd.DataFrame(rows)
    out.to_csv(OUT,index=False)

    print("="*116)
    print("A37.13 - COLLAPSED GEOMETRY SURVIVOR TEMPORAL/DIRECTION AUDIT")
    print("="*116)
    for cand in CANDIDATES:
        print(f"\n{cand}")
        print("-"*116)
        z=out[(out["candidate"].eq(cand)) & (out["split_type"].eq("QUARTER"))]
        if len(z):
            print(z[["quarter","baseline_n","baseline_ff_pct","candidate_n","candidate_ff_pct","lift_pp"]]
                  .to_string(index=False,float_format=lambda x:f"{x:.2f}"))
        else:
            print("No quarter cells with candidate N >= 8.")

    print("\nDIRECTION SUMMARY")
    print("-"*116)
    z=out[out["split_type"].eq("DIRECTION")]
    print(z[["candidate","direction","baseline_n","baseline_ff_pct","candidate_n","candidate_ff_pct","lift_pp"]]
          .to_string(index=False,float_format=lambda x:f"{x:.2f}"))

    print(f"\nFull output: {OUT}")
    print("RESULT: TEMPORAL/DIRECTION AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
