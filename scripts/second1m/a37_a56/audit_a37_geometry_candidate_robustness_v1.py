from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1/ae2_session_level_geometry_v1")
EVENTS = ROOT / "a37_session_level_geometry_events_v1.parquet"
THRESH = ROOT / "a37_geometry_discovery_quintile_thresholds_v1.csv"
OUT = ROOT / "a37_geometry_candidate_robustness_v1.csv"

BINARY = ["FAVORABLE_FIRST", "ADVERSE_FIRST"]

CANDIDATES = [
    ("POS", "c2_beyond_pm_pct", "Q2"),
    ("POS", "mean_pairwise_spacing_pct", "Q2"),
    ("POS", "level_cluster_span_pct_calc", "Q2"),
    ("POS", "directional_level_order_inner_to_outer", "PD>AH>PM"),
    ("POS", "c2_beyond_ah_pct", "Q2"),
    ("POS", "c2_beyond_outermost_pct", "Q3"),
    ("NEG", "c2_beyond_outermost_pct", "Q4"),
    ("NEG", "pm_pd_spacing_pct", "Q4"),
]

def rate(x):
    x = x[x["outcome"].isin(BINARY)]
    return len(x), 100.0 * x["outcome"].eq("FAVORABLE_FIRST").mean() if len(x) else np.nan

def main():
    e = pd.read_parquet(EVENTS)
    e = e[e["preferred_family"] & e["outcome"].isin(BINARY)].copy()
    t = pd.read_csv(THRESH)

    # Rebuild discovery quintile labels from frozen discovery cutpoints.
    qmaps = {}
    for metric, g in t.groupby("metric"):
        cuts = dict(zip(g["cutpoint"], g["value"]))
        if all(k in cuts for k in ["q20","q40","q60","q80"]):
            qmaps[metric] = [-np.inf, cuts["q20"], cuts["q40"], cuts["q60"], cuts["q80"], np.inf]

    rows = []
    for polarity, feature, state in CANDIDATES:
        if state.startswith("Q"):
            bins = qmaps[feature]
            mask = pd.cut(pd.to_numeric(e[feature], errors="coerce"),
                          bins=bins, labels=["Q1","Q2","Q3","Q4","Q5"],
                          include_lowest=True).astype("object").eq(state)
        else:
            mask = e[feature].astype(str).eq(state)

        for period in ["DISCOVERY","VALIDATION"]:
            base = e[e["research_period"].eq(period)]
            hit = e[e["research_period"].eq(period) & mask]
            bn, br = rate(base)
            hn, hr = rate(hit)
            rows.append({
                "polarity": polarity, "feature": feature, "state": state,
                "research_period": period, "candidate_n": hn,
                "candidate_ff_pct": hr, "baseline_n": bn,
                "baseline_ff_pct": br, "lift_pp": hr-br
            })

        # Directional and temporal validation stress tests.
        v = e[e["research_period"].eq("VALIDATION")].copy()
        vm = mask.loc[v.index]
        for split_name, split_col in [("DIRECTION","direction"),
                                      ("VALIDATION_SUBPERIOD","validation_subperiod")]:
            if split_col not in v.columns:
                continue
            for split, idx in v.groupby(split_col, dropna=False).groups.items():
                base = v.loc[idx]
                hit = v.loc[idx][vm.loc[idx]]
                bn, br = rate(base); hn, hr = rate(hit)
                if hn < 10:
                    continue
                rows.append({
                    "polarity": polarity, "feature": feature, "state": state,
                    "research_period": f"VALIDATION_{split_name}:{split}",
                    "candidate_n": hn, "candidate_ff_pct": hr,
                    "baseline_n": bn, "baseline_ff_pct": br, "lift_pp": hr-br
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)

    print("="*112)
    print("A37.10 - GEOMETRY CANDIDATE ROBUSTNESS / REDUNDANCY PRECHECK")
    print("="*112)
    mainrows = out[out["research_period"].isin(["DISCOVERY","VALIDATION"])]
    print(mainrows.to_string(index=False, float_format=lambda x:f"{x:.2f}"))
    print()
    print("VALIDATION STRESS CELLS (candidate N >= 10)")
    print("-"*112)
    stress = out[~out["research_period"].isin(["DISCOVERY","VALIDATION"])]
    print(stress.to_string(index=False, float_format=lambda x:f"{x:.2f}") if len(stress) else "NONE")
    print()
    print(f"Full output: {OUT}")
    print("RESULT: ROBUSTNESS PRECHECK COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
