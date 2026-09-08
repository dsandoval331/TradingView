from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
SRC = ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet"
OUTDIR = ROOT / "ae2_c1_c2_transition_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
BINARY = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}

FEATURES = [
    "c1_to_c2_close_progress_pct",
    "c2_to_c1_volume_ratio",
    "clv_change_pp",
    "vwap_distance_change_pp",
]

def ff_summary(df, group_cols):
    x = df[df["outcome"].isin(BINARY)].copy()
    x["ff"] = x["outcome"].eq("FAVORABLE_FIRST").astype(int)
    out = (
        x.groupby(group_cols, dropna=False, observed=True)
         .agg(binary_n=("ff","size"), favorable_n=("ff","sum"))
         .reset_index()
    )
    out["adverse_n"] = out["binary_n"] - out["favorable_n"]
    out["ff_pct"] = 100.0 * out["favorable_n"] / out["binary_n"]
    return out

def main():
    df = pd.read_parquet(SRC)
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    # Historical Preferred family only. No prospective data.
    x = df[
        df["outcome"].isin(BINARY)
        & df["session_level_clear_state"].eq("ALL_3_CLEARED")
        & df["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ].copy()

    # Preserve upstream frozen bucket intervals; only impose numeric order from interval left edge.
    rows = []
    for f in FEATURES:
        b = f + "__bucket"
        if b not in x.columns:
            raise KeyError(f"Missing frozen bucket: {b}")
        cats = list(pd.Series(x[b].dropna().unique()).sort_values(
            key=lambda s: s.map(lambda z: z.left if hasattr(z, "left") else float("-inf"))
        ))
        rank = {c: i+1 for i,c in enumerate(cats)}
        x[f + "__frozen_quintile"] = x[b].map(rank).astype("Int64")

        s = ff_summary(x, ["research_period", f + "__frozen_quintile"])
        s["feature"] = f
        rows.append(s)

    pooled = pd.concat(rows, ignore_index=True)
    pooled.to_csv(OUTDIR / "a39_transition_frozen_quintile_performance_v1.csv", index=False)

    # Direction stress is descriptive at this stage.
    drows = []
    for f in FEATURES:
        q = f + "__frozen_quintile"
        s = ff_summary(x, ["research_period", "direction", q])
        s["feature"] = f
        drows.append(s)
    bydir = pd.concat(drows, ignore_index=True)
    bydir.to_csv(OUTDIR / "a39_transition_frozen_quintile_direction_v1.csv", index=False)

    print("=" * 120)
    print("A39.3 - PREDECLARED C1->C2 TRANSITION SCREEN")
    print("=" * 120)
    print(f"Historical Preferred binary events: {len(x):,}")
    print()
    print("PREDECLARED HYPOTHESES")
    print("-" * 120)
    print("H-PROGRESS: stronger favorable C1->C2 close progress may indicate healthier continuation.")
    print("H-VOLUME:   higher C2/C1 volume participation may indicate healthier continuation.")
    print("H-CLV:      improving favorable CLV from C1->C2 may indicate healthier continuation.")
    print("H-VWAP:     increasing favorable VWAP distance may indicate strengthening momentum,")
    print("            but the extreme bucket may instead reveal extension/exhaustion.")
    print()
    print("No new cutpoints are searched. Existing upstream quintile buckets are used exactly.")
    print()

    for f in FEATURES:
        print("\n" + f)
        print("-" * 120)
        z = pooled[pooled["feature"].eq(f)].copy()
        cols = ["research_period", f + "__frozen_quintile",
                "binary_n","favorable_n","adverse_n","ff_pct"]
        print(z[cols].to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("\nRESULT: PREDECLARED TRANSITION SCREEN COMPLETE")
    print("Interpret only discovery/validation replication; do not create new thresholds from these results.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
