from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
PRED = ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet"
SESS = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
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
    z = df[df["outcome"].isin(BINARY)].copy()
    z["ff"] = z["outcome"].eq("FAVORABLE_FIRST").astype(int)
    out = (z.groupby(group_cols, dropna=False, observed=True)
             .agg(binary_n=("ff","size"), favorable_n=("ff","sum"))
             .reset_index())
    out["adverse_n"] = out["binary_n"] - out["favorable_n"]
    out["ff_pct"] = 100.0 * out["favorable_n"] / out["binary_n"]
    return out

def interval_left(v):
    return v.left if hasattr(v, "left") else float("-inf")

def main():
    pred = pd.read_parquet(PRED)
    sess = pd.read_parquet(SESS)
    for d in (pred, sess):
        d["trade_date"] = pd.to_datetime(d["trade_date"])

    preferred_keys = [
        "symbol","trade_date","direction","architecture",
        "decision_candle","entry_timestamp"
    ]
    keys = [k for k in preferred_keys if k in pred.columns and k in sess.columns]
    if len(keys) < 3:
        raise RuntimeError(f"Insufficient shared event keys: {keys}")

    # Classification + authoritative research split come from enriched session artifact.
    needed = [
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "research_period",
    ]
    missing = [c for c in needed if c not in sess.columns]
    if missing:
        raise KeyError(f"Session-level source missing required columns: {missing}")

    # Avoid merge suffix ambiguity if an upstream copy happens to exist.
    pred2 = pred.drop(columns=[c for c in needed if c in pred.columns], errors="ignore")
    sess_small = sess[keys + needed].drop_duplicates(keys)

    if sess_small.duplicated(keys).any():
        raise RuntimeError("Session-level artifact is not unique on selected event keys.")

    df = pred2.merge(sess_small, on=keys, how="left", validate="one_to_one")

    missing_class = int(df[needed].isna().any(axis=1).sum())

    print("=" * 120)
    print("A39.3 V1.2 - PREDECLARED C1->C2 TRANSITION SCREEN")
    print("=" * 120)
    print(f"Predictor source: {PRED}")
    print(f"Session-level source: {SESS}")
    print(f"Join keys: {keys}")
    print(f"Predictor rows: {len(pred):,}")
    print(f"Joined rows: {len(df):,}")
    print(f"Rows missing classification/research-period fields after join: {missing_class:,}")

    if len(df) != len(pred):
        raise RuntimeError(f"Row parity failed: predictor={len(pred)}, joined={len(df)}")
    if missing_class:
        raise RuntimeError(f"{missing_class} rows failed enrichment join.")

    x = df[
        df["outcome"].isin(BINARY)
        & df["session_level_clear_state"].eq("ALL_3_CLEARED")
        & df["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ].copy()

    print(f"Historical Preferred binary events: {len(x):,}")
    print("Preferred by research period:")
    print(x["research_period"].value_counts(dropna=False).to_string())

    rows = []
    for f in FEATURES:
        b = f + "__bucket"
        if b not in x.columns:
            raise KeyError(f"Missing frozen bucket: {b}")
        cats = sorted(list(x[b].dropna().unique()), key=interval_left)
        if len(cats) != 5:
            raise RuntimeError(f"{f}: expected 5 frozen buckets, found {len(cats)}")
        rank = {c: i+1 for i,c in enumerate(cats)}
        qcol = f + "__frozen_quintile"
        x[qcol] = x[b].map(rank).astype("Int64")
        s = ff_summary(x, ["research_period", qcol])
        s["feature"] = f
        rows.append(s)

    pooled = pd.concat(rows, ignore_index=True)
    pooled.to_csv(OUTDIR/"a39_transition_frozen_quintile_performance_v1.csv", index=False)

    drows = []
    for f in FEATURES:
        qcol = f + "__frozen_quintile"
        s = ff_summary(x, ["research_period","direction",qcol])
        s["feature"] = f
        drows.append(s)
    pd.concat(drows, ignore_index=True).to_csv(
        OUTDIR/"a39_transition_frozen_quintile_direction_v1.csv", index=False
    )

    print("\nPREDECLARED HYPOTHESES")
    print("-"*120)
    print("H-PROGRESS: stronger favorable C1->C2 close progress may indicate healthier continuation.")
    print("H-VOLUME:   higher C2/C1 volume participation may indicate healthier continuation.")
    print("H-CLV:      improving favorable CLV from C1->C2 may indicate healthier continuation.")
    print("H-VWAP:     increasing favorable VWAP distance may indicate strengthening momentum,")
    print("            while the extreme bucket may instead reveal extension/exhaustion.")
    print("\nNo new cutpoints are searched. Existing upstream quintile buckets are used exactly.")

    for f in FEATURES:
        qcol = f + "__frozen_quintile"
        print("\n" + f)
        print("-"*120)
        z = pooled[pooled["feature"].eq(f)]
        print(z[["research_period",qcol,"binary_n","favorable_n","adverse_n","ff_pct"]]
              .to_string(index=False, float_format=lambda v:f"{v:.2f}"))

    print("\nRESULT: PREDECLARED TRANSITION SCREEN COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
